"""Estimate rig joints of the Commando mesh at a rest frame (Blender object space, faces +X, height +Z)."""
import json
import numpy as np
SCALE = 0.02
import paths
MESH = paths.COMMANDO


def load(seq='Wave', frame=0):
    m = np.load(MESH)
    info = json.loads(str(m['info']))
    seqs = {s[0]: s for s in info['seqs']}
    F = m['frames'][seqs[seq][2] + frame].astype(np.float64)
    P = np.stack([F[:, 2], -F[:, 0], F[:, 1]], 1) * SCALE   # per original vertex
    return m, P


def analyse(seq='Wave', frame=0):
    m, P = load(seq, frame)
    faces, fmat, wv, uv = m['faces'], m['face_mat'], m['wedge_v'], m['wedge_uv']
    nv = P.shape[0]
    slot = np.full(nv, -1)
    vuv = np.zeros((nv, 2))
    for f, s in zip(faces, fmat):
        for w in f:
            slot[wv[w]] = s
            vuv[wv[w]] = uv[w]
    J = {}
    foot = P[3:, 2].min()
    J['foot_z'] = foot
    for side, sgn in (('L', 1), ('R', -1)):
        arm = (slot == 0) & (P[:, 1] * sgn > 0)
        A = P[arm]
        # glove = texture top 40% (UV v measured from bottom in Blender -> top rows have high v)
        gl = arm & (vuv[:, 1] > 0.60)
        shoulder = A[A[:, 2] > A[:, 2].max() - .06].mean(0)
        G = P[gl]
        wrist = G[G[:, 2] > G[:, 2].max() - .04].mean(0) if len(G) else A[A[:, 2].argmin()]
        hand = G.mean(0) if len(G) else wrist
        tip = G[G[:, 2].argmin()] if len(G) else wrist
        elbow = (shoulder + wrist) / 2
        # elbow: arm vertex nearest the mid height, pushed to the back surface average
        mid = A[np.abs(A[:, 2] - elbow[2]) < .04]
        if len(mid):
            elbow = mid.mean(0)
        J[side] = dict(shoulder=shoulder, elbow=elbow, wrist=wrist, hand=hand, tip=tip)
        leg = (P[:, 1] * sgn > 0) & (P[:, 2] < foot + .95) & (slot != 0)
        L = P[leg]
        sole = L[L[:, 2] < L[:, 2].min() + .05]
        ankle = sole.mean(0); ankle[2] = foot + .16
        toe = sole[sole[:, 0].argmax()].copy(); toe[2] = foot + .03
        knee_band = L[np.abs(L[:, 2] - (foot + .52)) < .05]
        knee = knee_band.mean(0)
        hip = np.array([P[:, 0].mean() * 0 + knee[0] * .3, sgn * .13, foot + .95])
        J[side].update(hip=hip, knee=knee, ankle=ankle, toe=toe)
    pelvis = (J['L']['hip'] + J['R']['hip']) / 2
    chest = (J['L']['shoulder'] + J['R']['shoulder']) / 2
    chest[2] -= .12
    head_top = P[P[:, 2].argmax()]  # antenna! use face slot instead
    face = (slot == 1) & (P[:, 2] > chest[2] + .1)
    H = P[face]
    J.update(pelvis=pelvis, chest=chest, neck=np.array([chest[0], 0, chest[2] + .16]),
             head=np.array([H[:, 0].mean(), 0, H[:, 2].max()]))
    return P, slot, vuv, J


if __name__ == '__main__':
    P, slot, vuv, J = analyse()
    np.set_printoptions(precision=3, suppress=True)
    for k, v in J.items():
        print(k, v)
    print('bounds', P.min(0), P.max(0))
