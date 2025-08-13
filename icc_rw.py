import struct
import numpy as np
class ICCProfile:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = bytearray(f.read())
        self.tags = self._read_tag_table()

    def _read_tag_table(self):
        count = struct.unpack('>I', self.data[128:132])[0]
        tags = {}
        for i in range(count):
            pos = 132 + i * 12
            tag = self.data[pos:pos+4].decode('ascii')
            offset = struct.unpack('>I', self.data[pos+4:pos+8])[0]
            size = struct.unpack('>I', self.data[pos+8:pos+12])[0]
            tags[tag] = {
                'offset': offset,
                'size': size,
                'index': i,
                'original_data': self.data[offset:offset+size]  # 关键：缓存原始数据
            }
        return tags

    def _decode_s15fixed16(self, raw: bytes) -> float:
        val = struct.unpack(">i", raw)[0]
        return val / 65536.0

    def _encode_s15fixed16(self, value: float) -> bytes:
        return struct.pack(">i", int(round(value * 65536)))

    def write_tag(self, tag_name: str, tag_bytes: bytes):
        # tag_name = tag_name.upper()
        if tag_name not in self.tags:
            self.tags[tag_name] = {
                'offset': 0,
                'size': len(tag_bytes),
                'index': max(t['index'] for t in self.tags.values()) + 1
            }
        # 对齐 tag 内容
        tag_bytes += b'\x00' * ((4 - len(tag_bytes) % 4) % 4)
        self.tags[tag_name]['new_data'] = tag_bytes

    def read_XYZType(self, tag):
        # tag = tag.upper()
        if tag not in self.tags: return None
        offset = self.tags[tag]['offset']
        values = []
        count = (self.tags[tag]['size'] - 8) // 12
        for i in range(count):
            base = offset + 8 + i * 12
            x, y, z = struct.unpack('>iii', self.data[base:base+12])
            values.append([x / 65536.0, y / 65536.0, z / 65536.0])
        return values

    def write_XYZType(self, tag, values):
        # tag = tag.upper()
        block = bytearray(b'XYZ ' + b'\x00\x00\x00\x00')
        for x, y, z in values:
            block += struct.pack('>iii', int(x * 65536), int(y * 65536), int(z * 65536))
        self.write_tag(tag, block)
    
    def read_textType(self, tag):
        if tag not in self.tags:
            return None
        offset = self.tags[tag]['offset']
        sig = self.data[offset:offset+4]
        if sig == b'desc':
            length = struct.unpack('>I', self.data[offset+8:offset+12])[0]
            return self.data[offset+12:offset+12+length].decode('ascii', errors='replace')
        elif sig == b'mluc':
            count = struct.unpack('>I', self.data[offset+8:offset+12])[0]
            records = []
            for i in range(count):
                base = offset + 16 + i * 12
                lang = self.data[base:base+2].decode('ascii')
                country = self.data[base+2:base+4].decode('ascii')
                length, roffset = struct.unpack('>II', self.data[base+4:base+12])
                text_bytes = self.data[offset+roffset : offset+roffset+length]
                text = text_bytes.decode('utf-16-be')
                records.append({'lang': lang, 'country': country, 'text': text})
            return records
        elif sig == b'text':  # 新增: 纯 textType (MSCA 使用)
            size = self.tags[tag]['size']
            raw = self.data[offset+8: offset+size]
            raw = raw.rstrip(b'\x00')
            return raw.decode('ascii', errors='replace')
        return None



    def write_textType(self, tag, value):
        if isinstance(value, str):
            # desc 用 'desc', 其它（如 MSCA）用 'text'
            sig = b'desc' if tag == 'desc' else b'text'
            encoded = value.encode('ascii', errors='ignore')
            block = sig + b'\x00\x00\x00\x00' + encoded
            # 4 字节对齐
            if len(block) % 4:
                block += b'\x00' * (4 - len(block) % 4)
            self.write_tag(tag, block)
        elif isinstance(value, list):
            # 仅 desc 支持 mluc 列表写入
            if tag not in ['desc', 'cprt']:
                raise ValueError("仅 'desc' 'cprt' 支持多语言写入")
            count = len(value)
            header = b'mluc' + b'\x00\x00\x00\x00' + struct.pack('>I', count) + struct.pack('>I', 12)
            records = bytearray()
            strings = bytearray()
            pos = 16 + count * 12
            for entry in value:
                lang = entry['lang'].encode('ascii')
                country = entry['country'].encode('ascii')
                encoded = entry['text'].encode('utf-16-be')
                pad = (4 - len(encoded) % 4) % 4
                records += lang + country + struct.pack('>II', len(encoded), pos)
                strings += encoded + b'\x00' * pad
                pos += len(encoded) + pad
            block = header + records + strings
            if len(block) % 4:
                block += b'\x00' * (4 - len(block) % 4)
            self.write_tag(tag, block)
        else:
            raise ValueError("文本写入仅支持 str 或（desc）多语言 list")
    
    def read_vcgt(self):
        """
        没测试
        读取 'vcgt' 标签.
        支持两种常见头格式:
        A) (Apple/某些工具) offset8..15 = rCount,gCount,bCount,bytesPerEntry
        B) (通用/另一格式)  offset8..15 = type(0/1), channels(1|3), entryCount, entrySize(bits)
           若 type=1 且 channels=3 -> 三通道表; entrySize=8/16
        返回 dict 或 None
        """
        tag = 'vcgt'
        if tag not in self.tags:
            return None
        off = self.tags[tag]['offset']
        size = self.tags[tag]['size']
        block = self.data[off:off+size]
        if size < 16 or block[0:4] != b'vcgt':
            return None

        # 读取头部四个 uint16
        if size >= 16:
            h1, h2, h3, h4 = struct.unpack(">HHHH", block[8:16])
        else:
            return None

        def read_channel_bytes(pos, count, bpe):
            raw = block[pos:pos + count * bpe]
            if len(raw) < count * bpe:
                return None
            if bpe == 1:
                return [v / 255.0 for v in raw]
            else:
                return [struct.unpack(">H", raw[i:i+2])[0] / 65535.0
                        for i in range(0, len(raw), 2)]

        # 尝试格式 A
        fmtA_ok = False
        vcgtA = None
        if h4 in (1, 2) and all(v > 0 for v in (h1, h2, h3)):
            # 认为是 r,g,b,count + bytesPerEntry
            bpe = h4
            r_count, g_count, b_count = h1, h2, h3
            expected = 16 + (r_count + g_count + b_count) * bpe
            if expected <= size:
                pos = 16
                r = read_channel_bytes(pos, r_count, bpe); pos += r_count * bpe
                g = read_channel_bytes(pos, g_count, bpe); pos += g_count * bpe
                b = read_channel_bytes(pos, b_count, bpe)
                if None not in (r, g, b):
                    fmtA_ok = True
                    vcgtA = {
                        "format": "A",
                        "red": r, "green": g, "blue": b,
                        "bytes_per_entry": bpe
                    }

        # 如果格式 A 失败，尝试格式 B
        if not fmtA_ok:
            v_type, channels, entry_count, entry_size_bits = h1, h2, h3, h4
            if v_type in (0, 1) and channels in (1, 3) and entry_size_bits in (8, 16) and entry_count > 0:
                bpe = entry_size_bits // 8
                total_entries = channels * entry_count
                expected = 16 + total_entries * bpe
                if expected <= size:
                    pos = 16
                    all_vals = read_channel_bytes(pos, total_entries, bpe)
                    if all_vals:
                        if channels == 1:
                            # 单通道，复制
                            r = g = b = all_vals
                        else:
                            r = all_vals[0:entry_count]
                            g = all_vals[entry_count:2*entry_count]
                            b = all_vals[2*entry_count:3*entry_count]
                        return {
                            "format": "B",
                            "type": v_type,
                            "red": r, "green": g, "blue": b,
                            "bytes_per_entry": bpe
                        }
            # 都不匹配
            return None

        return vcgtA

    def write_vcgt(self, red, green=None, blue=None, bytes_per_entry=2):
        """
        没测试
        写入/更新 'vcgt' 标签。
        red/green/blue: 可为长度相同的 list/ndarray(0~1). 若仅提供 red 且 green/blue 为 None, 复制为灰阶。
        bytes_per_entry: 1 或 2 (默认 16bit 精度).
        """
        tag = 'vcgt'
        red = list(red)
        if green is None: green = red
        if blue is None: blue = red
        if not (len(red) == len(green) == len(blue)):
            raise ValueError("vcgt 通道长度需一致")
        if bytes_per_entry not in (1, 2):
            raise ValueError("bytes_per_entry 仅支持 1 或 2")
        count = len(red)

        def clamp01(v): return 0.0 if v < 0 else (1.0 if v > 1 else v)

        def pack_channel(arr):
            if bytes_per_entry == 1:
                return bytes(int(round(clamp01(v) * 255)) & 0xFF for v in arr)
            else:
                out = bytearray()
                for v in arr:
                    out += struct.pack(">H", int(round(clamp01(v) * 65535)) & 0xFFFF)
                return bytes(out)

        payload = bytearray()
        # type signature + reserved
        payload += b'vcgt' + b'\x00\x00\x00\x00'
        # counts + bytesPerEntry
        payload += struct.pack(">HHHH", count, count, count, bytes_per_entry)
        payload += pack_channel(red)
        payload += pack_channel(green)
        payload += pack_channel(blue)
        self.write_tag(tag, bytes(payload))
    
    def read_MSCA(self):
        return self.read_textType('MSCA')

    def write_MSCA(self, text: str):
        """写入 MSCA 标签 (textType, 单文本)."""
        self.write_textType('MSCA', text)
    
    def read_desc(self):
        tag = 'desc'
        return self.read_textType(tag)

    def write_desc(self, value):
        tag = 'desc'
        self.write_textType(tag, value)

    def read_cprt(self):
        tag = 'cprt'
        return self.read_textType(tag)

    def write_cprt(self, value):
        tag = 'cprt'
        self.write_textType(tag, value)

    def read_MHC2(self):
        tag = 'MHC2'
        if tag not in self.tags:
            return None
        offset = self.tags[tag]['offset']
        block = self.data[offset:]
        if block[0:4] != b'MHC2':
            raise ValueError("Invalid MHC2 signature")

        count = struct.unpack(">I", block[8:12])[0]
        min_lum = self._decode_s15fixed16(block[12:16])
        peak_lum = self._decode_s15fixed16(block[16:20])
        # matrix_offset = struct.unpack(">I", block[20:24])[0]
        matrix_offset = struct.unpack(">I", self.data[offset + 20:offset + 24])[0]
        red_offset = struct.unpack(">I", block[24:28])[0]
        green_offset = struct.unpack(">I", block[28:32])[0]
        blue_offset = struct.unpack(">I", block[32:36])[0]

        def read_lut(offset):
            if offset == 0: return None
            if block[offset:offset+4] != b'sf32': return None
            return [
                self._decode_s15fixed16(block[offset+8+i:offset+12+i])
                for i in range(0, count*4, 4)
            ]

        matrix = None
        if matrix_offset:
            mdata = self.data[offset + matrix_offset : offset + matrix_offset + 48]
            raw = [self._decode_s15fixed16(mdata[i:i+4]) for i in range(0, 48, 4)]
            matrix = [raw[i] for i in range(12) if i % 4 != 3]
        

        return {
            'entry_count': count,
            'min_luminance': min_lum,
            'peak_luminance': peak_lum,
            'matrix': matrix,
            'red_lut': read_lut(red_offset),
            'green_lut': read_lut(green_offset),
            'blue_lut': read_lut(blue_offset),
        }

    def write_MHC2(self, mhc2_data):
        tag = 'MHC2'
        if tag not in self.tags:
            raise ValueError("MHC2 tag missing")
        count = mhc2_data['entry_count']
        matrix = mhc2_data.get('matrix')
        r, g, b = mhc2_data.get('red_lut'), mhc2_data.get('green_lut'), mhc2_data.get('blue_lut')

        block = bytearray()
        block += b'MHC2' + b'\x00\x00\x00\x00'
        block += struct.pack(">I", count)
        block += self._encode_s15fixed16(mhc2_data["min_luminance"])
        block += self._encode_s15fixed16(mhc2_data["peak_luminance"])

        # 占位 4 个 offset
        offset_base = len(block)
        block += b'\x00' * 16  # matrix, red, green, blue offset

        sub_blocks = {}

        # 写 matrix
        if matrix:
            assert len(matrix) == 9
            pos = len(block)
            sub_blocks['matrix'] = pos
            for i in range(3):
                for j in range(3):
                    block += self._encode_s15fixed16(matrix[i*3 + j])
                block += self._encode_s15fixed16(0.0)
            if len(block) % 4 != 0:
                block += b'\x00' * (4 - len(block) % 4)

        def write_lut(name, lut, block):
            if not lut:
                return
            pos = len(block)
            sub_blocks[name] = pos
            block.extend(b'sf32' + b'\x00\x00\x00\x00')
            for v in lut:
                block += self._encode_s15fixed16(v)
            if len(block) % 4 != 0:
                block += b'\x00' * (4 - len(block) % 4)

        write_lut('red', r, block)
        write_lut('green', g, block)
        write_lut('blue', b, block)

        # 回填 offsets
        def set_offset(pos, val):
            block[offset_base + pos : offset_base + pos + 4] = struct.pack(">I", val)

        set_offset(0, sub_blocks.get("matrix", 0))
        set_offset(4, sub_blocks.get("red", 0))
        set_offset(8, sub_blocks.get("green", 0))
        set_offset(12, sub_blocks.get("blue", 0))

        # 写入 tag 数据
        self.write_tag(tag, block)

    # ================= RGB TRC (rTRC/gTRC/bTRC) 全量读写支持 =================
    # 支持:
    #   curveType  (curv) count==1  -> gamma
    #   curveType  (curv) count>1   -> 离散曲线 (uInt16 0..65535)
    #   parametricCurveType (para) functionType 0..4
    # 写入:
    #   write_TRC(tag, data, mode='auto'|'gamma'|'curve'|'param')
    #   data 可以是:
    #       float (gamma)
    #       {'type':'gamma','gamma':2.2}
    #       {'type':'curve','values':[...0..1...]}
    #       {'type':'parametric','functionType':0..4,'params':[...]}
    # 读取:
    #   read_TRC(tag) 返回:
    #       {'type':'gamma','gamma':g}
    #       {'type':'curve','values':[...]}
    #       {'type':'parametric','functionType':n,'params':[...],'eval':callable}
    #   不支持或损坏 -> None
    #
    # 备注: 未修改的未知 TRC 会原样保留 (不调用 write_TRC 即可)

    def _read_TRC_curve(self, off, size):
        if size < 14:  # signature+reserved+count(4)+至少1个uint16
            return None
        count = struct.unpack(">I", self.data[off+8:off+12])[0]
        if count == 0:
            return {'type': 'curve', 'values': []}
        # 位置
        start = off + 12
        end = start + count * 2
        if end > off + size:
            return None
        vals = struct.unpack(">" + "H"*count, self.data[start:end])
        if count == 1:
            # gamma = value / 256
            g = vals[0] / 256.0 if vals[0] > 0 else 1.0
            return {'type': 'gamma', 'gamma': g}
        else:
            arr = [v / 65535.0 for v in vals]
            return {'type': 'curve', 'values': arr}

    def _read_TRC_parametric(self, off, size):
        if size < 16:
            return None
        func_type = struct.unpack(">H", self.data[off+8:off+10])[0]
        if func_type > 4:  # 只支持 0..4
            return None
        param_counts = {0:1, 1:3, 2:4, 3:5, 4:7}
        need = param_counts[func_type]
        expected_bytes = 12 + need * 4
        if size < expected_bytes:
            return None
        params = []
        pos = off + 12
        for _ in range(need):
            params.append(self._decode_s15fixed16(self.data[pos:pos+4]))
            pos += 4

        def _eval(x):
            x = np.asarray(x, dtype=float)
            x = np.clip(x, 0.0, 1.0)
            if func_type == 0:
                g = params[0]
                return np.power(x, g, where=x>0)
            if func_type == 1:
                g,a,b = params
                cut = -b / a if a != 0 else -1e9
                y = np.zeros_like(x)
                mask = x >= cut
                y[mask] = np.power(a*x[mask] + b, g, where=(a*x[mask]+b)>0)
                return y
            if func_type == 2:
                g,a,b,c = params
                cut = -b / a if a != 0 else -1e9
                y = np.full_like(x, c)
                mask = x >= cut
                y[mask] = np.power(a*x[mask] + b, g, where=(a*x[mask]+b)>0) + c
                return y
            if func_type == 3:
                g,a,b,c,d = params
                y = np.empty_like(x)
                mask = x >= d
                y[mask] = np.power(a*x[mask] + b, g, where=(a*x[mask]+b)>0)
                y[~mask] = c * x[~mask]
                return y
            if func_type == 4:
                g,a,b,c,d,e,f = params
                y = np.empty_like(x)
                mask = x >= d
                y[mask] = np.power(a*x[mask] + b, g, where=(a*x[mask]+b)>0) + e
                y[~mask] = c * x[~mask] + f
                return y
            return x

        return {
            'type': 'parametric',
            'functionType': func_type,
            'params': params,
            'eval': _eval
        }

    def read_TRC(self, tag):
        if tag not in self.tags:
            return None
        info = self.tags[tag]
        off, size = info['offset'], info['size']
        if size < 12:
            return None
        sig = self.data[off:off+4]
        if sig == b'curv':
            return self._read_TRC_curve(off, size)
        if sig == b'para':
            return self._read_TRC_parametric(off, size)
        return None  # 其他类型未支持

    def read_rgbTRC(self):
        """
        返回:
            {
              'rTRC': {...} or None,
              'gTRC': {...} or None,
              'bTRC': {...} or None
            }
        各通道结构同 read_TRC:
            {'type':'gamma','gamma':g}
            {'type':'curve','values':[...]}
            {'type':'parametric','functionType':n,'params':[...],'eval':callable}
        """
        return {
            'rTRC': self.read_TRC('rTRC'),
            'gTRC': self.read_TRC('gTRC'),
            'bTRC': self.read_TRC('bTRC')
        }

    # ---------------- 写入 ----------------
    def _write_curve_gamma(self, tag, gamma: float, prefer_parametric=True):
        if prefer_parametric:
            # parametric functionType=0
            block = bytearray()
            block += b'para' + b'\x00\x00\x00\x00'
            block += struct.pack(">H", 0)  # functionType
            block += b'\x00\x00'          # reserved
            block += self._encode_s15fixed16(float(gamma))
            if len(block) % 4: block += b'\x00'*(4-len(block)%4)
            self.write_tag(tag, block)
        else:
            # curveType count=1
            val = int(round(float(gamma)*256))
            val = max(1, min(val, 0xFFFF))
            block = bytearray()
            block += b'curv' + b'\x00\x00\x00\x00'
            block += struct.pack(">I", 1)
            block += struct.pack(">H", val)
            if len(block) % 4: block += b'\x00'*(4-len(block)%4)
            self.write_tag(tag, block)

    def _write_curve_samples(self, tag, values):
        vals = np.asarray(values, dtype=float)
        if vals.ndim != 1 or vals.size == 0:
            raise ValueError("curve values must be 1-D non-empty")
        vals = np.clip(vals, 0.0, 1.0)
        block = bytearray()
        block += b'curv' + b'\x00\x00\x00\x00'
        block += struct.pack(">I", vals.size)
        for v in vals:
            block += struct.pack(">H", int(round(v * 65535)) & 0xFFFF)
        if len(block) % 4: block += b'\x00'*(4-len(block)%4)
        self.write_tag(tag, block)

    def _write_curve_parametric(self, tag, functionType, params):
        # functionType: 0..4
        param_counts = {0:1,1:3,2:4,3:5,4:7}
        if functionType not in param_counts:
            raise ValueError("Unsupported functionType")
        need = param_counts[functionType]
        if len(params) != need:
            raise ValueError(f"functionType {functionType} requires {need} params")
        block = bytearray()
        block += b'para' + b'\x00\x00\x00\x00'
        block += struct.pack(">H", functionType)
        block += b'\x00\x00'
        for p in params:
            block += self._encode_s15fixed16(float(p))
        if len(block) % 4: block += b'\x00'*(4-len(block)%4)
        self.write_tag(tag, block)

    def write_TRC(self, tag, data, mode='auto', prefer_parametric_gamma=True):
        """
        写入单个 TRC:
            data:
                float -> gamma
                {'type':'gamma','gamma':g}
                {'type':'curve','values':[...]}
                {'type':'parametric','functionType':n,'params':[...]}
            mode:
                'auto'  根据 data 决定
                'gamma' 强制按 gamma 写
                'curve' 强制按 curve 写
                'param' 强制按 parametric 写
        """
        # 归一化 data
        if isinstance(data, (int, float)):
            data = {'type':'gamma','gamma':float(data)}
        if not isinstance(data, dict) or 'type' not in data:
            raise ValueError("Unsupported TRC data format")

        tp = data['type']
        if mode != 'auto':
            # 强制模式映射
            if mode == 'gamma':
                tp = 'gamma'
            elif mode == 'curve':
                tp = 'curve'
            elif mode in ('param','parametric'):
                tp = 'parametric'
            else:
                raise ValueError("mode must be auto/gamma/curve/param")

        if tp == 'gamma':
            g = float(data.get('gamma', 2.2))
            self._write_curve_gamma(tag, g, prefer_parametric=prefer_parametric_gamma)
        elif tp == 'curve':
            values = data.get('values')
            if values is None:
                raise ValueError("curve data missing 'values'")
            self._write_curve_samples(tag, values)
        elif tp == 'parametric':
            ft = int(data.get('functionType', 0))
            params = data.get('params')
            if params is None:
                raise ValueError("parametric data missing 'params'")
            self._write_curve_parametric(tag, ft, params)
        else:
            raise ValueError("Unknown TRC type")

    def write_rgbTRC(self, data=None, mode='auto', prefer_parametric_gamma=True):
        """
        仅接受与 read_rgbTRC 相同格式的整体字典:
            data = {
               'rTRC': {'type':...},
               'gTRC': {'type':...},
               'bTRC': {'type':...}
            }
        """
        # 若提供整体 data，拆出
        if data is not None:
            if not isinstance(data, dict):
                raise ValueError("data 必须是包含 rTRC/gTRC/bTRC 的字典")
            rTRC = data.get('rTRC')
            gTRC = data.get('gTRC')
            bTRC = data.get('bTRC')

        if not(rTRC and gTRC and bTRC):
            raise ValueError("rgbTRC数据不完整")

        # 实际写入
        self.write_TRC('rTRC', rTRC, mode=mode, prefer_parametric_gamma=prefer_parametric_gamma)
        self.write_TRC('gTRC', gTRC, mode=mode, prefer_parametric_gamma=prefer_parametric_gamma)
        self.write_TRC('bTRC', bTRC, mode=mode, prefer_parametric_gamma=prefer_parametric_gamma)
    # ================== /RGB TRC 支持结束 ==================

    def read_all(self):
        return {
            'desc': self.read_desc(),
            'rXYZ': self.read_XYZType('rXYZ'),
            'gXYZ': self.read_XYZType('gXYZ'),
            'bXYZ': self.read_XYZType('bXYZ'),
            'wtpt': self.read_XYZType('wtpt'),
            'lumi': self.read_XYZType('lumi'),
            'MHC2': self.read_MHC2(),
            'cprt': self.read_cprt(),
            'MSCA': self.read_MSCA(),        
            'rgbTRC': self.read_rgbTRC(),
        }

    def write_all(self, desc=None, rXYZ=None, gXYZ=None, bXYZ=None,
                  wtpt=None, lumi=None, MHC2=None, cprt=None,
                  MSCA=None, rgbTRC=None, trc_mode='auto'):
        if desc is not None: self.write_desc(desc)
        if rXYZ is not None: self.write_XYZType('rXYZ', rXYZ)
        if gXYZ is not None: self.write_XYZType('gXYZ', gXYZ)
        if bXYZ is not None: self.write_XYZType('bXYZ', bXYZ)
        if wtpt is not None: self.write_XYZType('wtpt', wtpt)
        if lumi is not None: self.write_XYZType('lumi', lumi)
        if MHC2 is not None: self.write_MHC2(MHC2)
        if cprt is not None: self.write_cprt(cprt)
        if MSCA is not None: self.write_MSCA(MSCA)
        if rgbTRC is not None:
            self.write_rgbTRC(data=rgbTRC, mode=trc_mode)

    def rebuild(self):
        # 拷贝 ICC header（前128字节）
        header = self.data[:128]
        tag_count = len(self.tags)

        # 构建 tag table（tag count + 每个tag的entry）
        tag_table = bytearray(struct.pack('>I', tag_count))
        content = bytearray()
        offset = 128 + 4 + tag_count * 12

        # 按原始顺序排序 tag（保留写入顺序）
        for tag, info in sorted(self.tags.items(), key=lambda x: x[1]['index']):
            # 优先使用 new_data，否则使用 original_data
            data = info.get('new_data', info.get('original_data'))
            if data is None:
                raise ValueError(f"Tag {tag} has no data available")

            # 对齐 tag 内容到 4 字节
            if len(data) % 4 != 0:
                data += b'\x00' * (4 - len(data) % 4)

            # 添加 tag entry
            tag_table += tag.encode('ascii')
            tag_table += struct.pack('>II', offset, len(data))

            # 添加 tag 数据块
            content += data
            offset += len(data)

        # 构建最终数据
        final = header + tag_table + content

        # 修正 header 中的文件大小（bytes 0–3）
        final[0:4] = struct.pack('>I', len(final))

        # 更新 self.data
        self.data = final

        # rebuild 后应重新生成 tag 表
        self.tags = self._read_tag_table()

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.data)



if __name__ == "__main__":
    import copy
    icc = ICCProfile("C:\\Windows\\System32\\spool\\drivers\\color\\nm1_黑_16.icc")
    data = icc.read_all()
    for k,v in enumerate(data["MHC2"]["red_lut"][:100]):
        print(f"{k/1023}: {v}")
    print()
