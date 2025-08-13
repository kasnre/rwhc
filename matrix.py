import numpy as np
from convert_utils import *


def build_rgb_to_xyz_from_primaries(xy_R, xy_G, xy_B, xy_W):
    """
    用色域定义（原色 xy 与白点 xy）构造 RGB(linear) -> XYZ 矩阵
    """
    XYZ_R = xyY_to_XYZ([*xy_R, 10000])
    XYZ_G = xyY_to_XYZ([*xy_G, 10000])
    XYZ_B = xyY_to_XYZ([*xy_B, 10000])
    XYZ_W = xyY_to_XYZ([*xy_W, 10000])
    M0 = np.column_stack([XYZ_R, XYZ_G, XYZ_B])   # 3x3，列为各原色的 XYZ(相对Y=1)
    s = np.linalg.solve(M0, XYZ_W)          # 列缩放使 M@[1,1,1]=XW
    M = M0 @ np.diag(s)
    return M

def build_xyz_to_rgb_from_primaries(xy_R, xy_G, xy_B, xy_W):
    """
    用色域定义（原色 xy 与白点 xy）构造 XYZ -> RGB(linear) 矩阵。
    """
    M_rgb2xyz = build_rgb_to_xyz_from_primaries(xy_R, xy_G, xy_B, xy_W)
    return np.linalg.inv(M_rgb2xyz)


def calc_rgb_mapping_matrix(source_primaries, target_primaries):
    """
    计算从 source_primaries 到 target_primaries 的RGB线性映射矩阵
    白点直接取各自 primaries["white"]
    """
    M_source = np.array([source_primaries["red"],
                         source_primaries["green"],
                         source_primaries["blue"]]).T

    W = np.array(source_primaries["white"])
    S = np.linalg.inv(M_source) @ W
    M_source = M_source * S

    M_target = np.array([target_primaries["red"],
                         target_primaries["green"],
                         target_primaries["blue"]]).T
    W = np.array(target_primaries["white"])
    S = np.linalg.inv(M_target) @ W
    M_target = M_target * S
    
    mapping = M_target @ np.linalg.inv(M_source)
    return mapping

def calc_rgb_mapping_matrix_non_normalized(source_primaries, target_primaries):
    """
    计算从 source_primaries 到 target_primaries 的RGB线性映射矩阵
    """
    M_source = np.array([source_primaries["red"],
                         source_primaries["green"],
                         source_primaries["blue"]]).T

    M_target = np.array([target_primaries["red"],
                         target_primaries["green"],
                         target_primaries["blue"]]).T

    mapping = M_target @ np.linalg.inv(M_source)
    return mapping


def fit_XYZ2XYZ_wlock(XYZ_measured, XYZ_target, XYZ_w_measured, XYZ_w_target, w=None, l2=0.0):
    """
    拟合 3x3 矩阵 C，使得 C @ X_meas ≈ X_tgt，并满足白点硬约束 C @ Xw_meas = Xw_tgt。
    参数:
      X_meas: (n,3)  每个样本的实测 XYZ
      X_tgt : (n,3)  每个样本的目标 XYZ
      Xw_meas: (3,)  实测白点 XYZ
      Xw_tgt : (3,)  目标白点 XYZ（同一单位/尺度）
      w: (n,) 或 None  每个样本的权重（可选）
      l2: float        L2 正则强度（可选，0 即无正则）
    返回:
      C: (3,3)  校正矩阵（XYZ→XYZ）
    """
    XYZ_measured = np.asarray(XYZ_measured, float)
    XYZ_target  = np.asarray(XYZ_target,  float)
    XYZ_w_measured = np.asarray(XYZ_w_measured, float).reshape(3)
    XYZ_w_target  = np.asarray(XYZ_w_target,  float).reshape(3)
    n = XYZ_measured.shape[0]
    I3 = np.eye(3)

    # 构造普通样本的 A、b：  vec(C) 的未知量个数=9
    # 对每个样本 i： (I3 ⊗ X_meas[i]^T) · vec(C) ≈ X_tgt[i]
    A = np.zeros((3*n, 9))
    b = XYZ_target.reshape(-1)
    for i in range(n):
        xi = XYZ_measured[i].reshape(1,3)               # (1,3)
        A[3*i:3*i+3, :] = np.kron(I3, xi)         # (3,9)

    # 加权（可选）
    if w is not None:
        w = np.asarray(w, float).reshape(-1)
        W = np.repeat(np.sqrt(w), 3)              # 对XYZ 3维同步加权
        A = A * W[:,None]
        b = b * W

    # 白点硬约束： C @ Xw_meas = Xw_tgt
    # 约束矩阵 Cc 满足： (I3 ⊗ Xw_meas^T) · vec(C) = Xw_tgt
    Cc = np.kron(I3, XYZ_w_measured.reshape(1,3))        # (3,9)
    d  = XYZ_w_target.reshape(3)

    # L2 正则（可选）：在 ATA 对角线上加 l2
    ATA = A.T @ A
    ATb = A.T @ b
    if l2 > 0:
        ATA = ATA + l2 * np.eye(9)

    # 组装 KKT 系统：
    # [ ATA   Cc^T ] [m]   = [ATb]
    # [ Cc     0  ] [λ]     [ d ]
    KKT = np.block([
        [ATA,        Cc.T],
        [Cc,  np.zeros((3,3))]
    ])
    rhs = np.concatenate([ATb, d])

    sol = np.linalg.solve(KKT, rhs)
    m = sol[:9]  # vec(C)
    # 注意这里 vec 是按行块构造的： (I3 ⊗ x^T)，因此还原时用行优先
    C = m.reshape(3,3, order='C')
    return C

def fit_XYZ2XYZ_wlock_dropY(XYZ_measured, XYZ_target, XYZ_w_measured, XYZ_w_target, w=None, l2=0.0):
    XYZ_measured = np.asarray(XYZ_measured, float)
    XYZ_target  = np.asarray(XYZ_target,  float)
    XYZ_w_measured = np.asarray(XYZ_w_measured, float).reshape(3)
    XYZ_w_target  = np.asarray(XYZ_w_target,  float).reshape(3)
    if XYZ_measured.ndim != 2 or XYZ_measured.shape[1] != 3 or XYZ_target.shape != XYZ_measured.shape:
        raise ValueError("X_meas/X_tgt must be (n,3) with the same shape")

    xy_measured = XYZ_to_xy(XYZ_measured)  # (n,2) with possible nan for invalid rows
    xy_target  = XYZ_to_xy(XYZ_target)
    xy_w_measured = XYZ_to_xy(XYZ_w_measured)
    xy_w_target  = XYZ_to_xy(XYZ_w_target)

    valid = (
        np.all(np.isfinite(xy_measured), axis=1) &
        np.all(np.isfinite(xy_target),  axis=1) &
        (xy_measured[:, 1] > 0) &
        (xy_target[:,  1] > 0)
    )
    if not np.any(valid):
        raise ValueError("No valid samples after xy conversion")

    xy_measured = xy_measured[valid]
    xy_target  = xy_target[valid]
    

    Y_abs = 10.0
    xyY_measured = np.column_stack([xy_measured, np.full(xy_measured.shape[0], Y_abs, dtype=float)])
    xyY_target  = np.column_stack([xy_target,  np.full(xy_target.shape[0],  Y_abs, dtype=float)])

    xyz_measured_fixed = xyY_to_XYZ(xyY_measured)  
    xyz_target_fixed  = xyY_to_XYZ(xyY_target)
    xyz_w_measured_fixed = xyY_to_XYZ([*xy_w_measured, Y_abs])
    xyz_w_target_fixed  = xyY_to_XYZ([*xy_w_target,  Y_abs])

    ww = None
    if w is not None:
        w = np.asarray(w, float).reshape(-1)
        if w.size != XYZ_measured.shape[0]:
            raise ValueError("weights length mismatch")
        ww = w[valid]

    C = fit_XYZ2XYZ_wlock(xyz_measured_fixed, xyz_target_fixed, xyz_w_measured_fixed, xyz_w_target_fixed, w=ww, l2=l2)
    return C

def fit_XYZ2XYZ_dropY(XYZ_measured, XYZ_target, w=None, l2=0.0):
    XYZ_measured = np.asarray(XYZ_measured, float)
    XYZ_target  = np.asarray(XYZ_target,  float)
    if XYZ_measured.ndim != 2 or XYZ_measured.shape[1] != 3 or XYZ_target.shape != XYZ_measured.shape:
        raise ValueError("X_meas/X_tgt must be (n,3) with the same shape")

    xy_measured = XYZ_to_xy(XYZ_measured)  # (n,2) with possible nan for invalid rows
    xy_target  = XYZ_to_xy(XYZ_target)

    valid = (
        np.all(np.isfinite(xy_measured), axis=1) &
        np.all(np.isfinite(xy_target),  axis=1) &
        (xy_measured[:, 1] > 0) &
        (xy_target[:,  1] > 0)
    )
    if not np.any(valid):
        raise ValueError("No valid samples after xy conversion")

    xy_measured = xy_measured[valid]
    xy_target  = xy_target[valid]

    Y_abs = 10.0
    xyY_measured = np.column_stack([xy_measured, np.full(xy_measured.shape[0], Y_abs, dtype=float)])
    xyY_target  = np.column_stack([xy_target,  np.full(xy_target.shape[0],  Y_abs, dtype=float)])

    X_meas_fixed = xyY_to_XYZ(xyY_measured)  
    X_tgt_fixed  = xyY_to_XYZ(xyY_target)

    ww = None
    if w is not None:
        w = np.asarray(w, float).reshape(-1)
        if w.size != XYZ_measured.shape[0]:
            raise ValueError("weights length mismatch")
        ww = w[valid]

    C = fit_XYZ2XYZ(X_meas_fixed, X_tgt_fixed, w=ww, l2=l2)
    return C

def fit_XYZ2XYZ(XYZ_measured, XYZ_target, w=None, l2=0.0):
    """
    Unconstrained fit of a 3x3 matrix C such that C @ X_meas ≈ X_tgt
    (no white-point hard constraint).
    Args:
      X_meas: (n,3) measured XYZ samples
      X_tgt : (n,3) target XYZ samples
      w: optional (n,) weights
      l2: optional L2 regularization (scalar)
    Returns:
      C: (3,3) mapping matrix
    """
    XYZ_measured = np.asarray(XYZ_measured, float)
    XYZ_target  = np.asarray(XYZ_target,  float)
    n = XYZ_measured.shape[0]
    if n == 0:
        raise ValueError("No samples provided")

    I3 = np.eye(3)
    # Build A (3n x 9) and b (3n,)
    A = np.zeros((3 * n, 9))
    b = XYZ_target.reshape(-1)
    for i in range(n):
        xi = XYZ_measured[i].reshape(1, 3)
        A[3*i:3*i+3, :] = np.kron(I3, xi)

    # Apply weights if given (same scheme as white-lock version)
    if w is not None:
        w = np.asarray(w, float).reshape(-1)
        if w.size != n:
            raise ValueError("weights length mismatch")
        W = np.repeat(np.sqrt(w), 3)
        A = A * W[:, None]
        b = b * W

    ATA = A.T @ A
    ATb = A.T @ b
    if l2 > 0:
        ATA = ATA + l2 * np.eye(9)

    # Solve normal equations; fallback to lstsq if singular
    try:
        m = np.linalg.solve(ATA, ATb)
    except np.linalg.LinAlgError:
        m, *_ = np.linalg.lstsq(A, b, rcond=None)

    C = m.reshape(3, 3, order='C')
    return C


if __name__ == "__main__":
    X_meas = [[0.0078652003, 0.008075561, 0.006818738500000001], [0.0069408186, 0.008730198900000001, 0.0051397427], [0.0079000496, 0.0092610949, 0.0047605614], [0.0065731655, 0.007169774099999999, 0.0098863041], [0.007509592000000001, 0.0089061028, 0.010106587700000001], [0.0056101579, 0.0044552922000000005, 0.0027226421], [0.007878178, 0.008971732, 0.0041017991], [0.0061226825, 0.0051003034, 0.0095902299], [0.0046982521, 0.0031712193, 0.0001316159], [4.4054900000000004e-05, 4.57357e-05, 6.489509999999999e-05], [4.40254e-05, 4.57186e-05, 6.48683e-05], [4.4023800000000004e-05, 4.56963e-05, 6.48454e-05], [4.4021500000000005e-05, 4.56914e-05, 6.48329e-05], [0.0055001202999999995, 0.0080246046, 0.0047528409], [0.0053988231, 0.0034796068, 0.0039944026], [0.0058462124, 0.006222207499999999, 0.006553691600000001], [0.0082832403, 0.0088134912, 0.0093092413], [0.0100569658, 0.0107003057, 0.0112877289], [0.0114737568, 0.012209679, 0.012860023799999998], ]
    X_tgt = [[0.01576605838519226, 0.014793345271452893, 0.009970309415828525], [0.01092674840436487, 0.017306340640453676, 0.005700912210972972], [0.015499428779093122, 0.019454179936645232, 0.004993372673676908], [0.010122452212660907, 0.011328531625233272, 0.02162328089683309], [0.012364366516017099, 0.017581398801256382, 0.022224557535119344], [0.011399097897517363, 0.006361368324091146, 0.001995336027121758], [0.016239494708729617, 0.018515338385249918, 0.0038187885419577947], [0.01045186609319093, 0.006637316424143144, 0.02105631417314377], [0.010579597633660915, 0.004978634180546313, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.006487197794573525, 0.015243580002886758, 0.004965509423006897], [0.011279869700242579, 0.00525026662411291, 0.003978717676085563], [0.008110132510765956, 0.00853288646, 0.009292806135617022], [0.016220265021531913, 0.01706577292, 0.018585612271234044], [0.02433039753229787, 0.02559865938, 0.027878418406851062], [0.032440530043063825, 0.03413154584, 0.03717122454246809], ]
    Xw_meas = [0.012110873599999999, 0.0128726612, 0.0136013749]
    Xw_tgt = [0.0364955962984468, 0.03839798907, 0.041817627610276596]
    matrix = fit_XYZ2XYZ_wlock(X_meas, X_tgt, Xw_meas, Xw_tgt, w=None, l2=0.0)
    print(matrix)
    #  [3.046855885594285, -1.1025808519457923, 1.0231538998117535, 
    # -0.5791400694145858, 2.383822764075156, 1.0895824666411102, 
    # -0.31415750390541, -0.9171359761187199, 4.249629148091815]
    rgb = np.array([0.5,0.5,0.5])
    xyz = matrix @ rgb
    print(xyz)
    
    