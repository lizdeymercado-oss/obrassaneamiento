#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diseño estructural preliminar de tanques rectangulares de concreto reforzado.
Criterios: NSR-10 (Títulos A, B, C, H) y ACI 350 (estructuras para líquidos).

Uso:
    python diseno_tanques.py                 # modo interactivo (pregunta los datos)
    python diseno_tanques.py --demo          # ejemplo con valores por defecto
    python diseno_tanques.py --graficos      # además muestra/guarda los esquemas
    python diseno_tanques.py --demo --auto   # ajusta dimensiones hasta cumplir

Requiere Python 3.8+. Para los esquemas: pip install matplotlib

RESULTADO PRELIMINAR: debe ser revisado y firmado por un ingeniero civil /
estructural con matrícula profesional (Ley 400 de 1997).
"""
import argparse
import math
import re
from dataclasses import dataclass, replace
from typing import Optional

GW = 9.81      # peso unitario del agua, kN/m3
GC = 24.0      # peso unitario del concreto, kN/m3
SD = 1.3       # factor de durabilidad en flexión (ACI 350)
BARS = [("#4", 129), ("#5", 199), ("#6", 284), ("#7", 387)]  # área en mm2


@dataclass
class Datos:
    enterrado: bool = True
    cerrado: bool = True
    nf: Optional[float] = None      # profundidad del nivel freático (m); None = no existe
    V: float = 100.0                # volumen útil (m3)
    H: float = 3.5                  # altura de agua (m)
    r: float = 1.5                  # relación largo/ancho
    Hc: float = 0.5                 # tierra sobre la tapa (m)
    qs: float = 10.0                # sobrecarga (kN/m2)
    fc: float = 28.0                # MPa
    fy: float = 420.0               # MPa
    gs: float = 18.0                # peso unitario del suelo (kN/m3)
    phi: float = 30.0               # fricción del suelo (°)
    qa: float = 150.0               # capacidad portante admisible (kPa)
    Aa: float = 0.15
    Fa: float = 1.2
    I: float = 1.5
    eM: Optional[float] = None      # espesor de muros manual (m)
    eF: Optional[float] = None      # espesor de losa de fondo manual (m)
    eT: Optional[float] = None      # espesor de tapa manual (m)
    vo: float = 0.0                 # voladizo de la losa de fondo (m)


# ----------------------------------------------------------------- utilidades
def as_req(Mu, d, fc, fy):
    """Acero requerido (mm2/m) para Mu en kN·m/m y d en m. None si no alcanza."""
    Rn = Mu / (0.9 * d * d) / 1000.0
    q = 1 - 2 * Rn / (0.85 * fc)
    if q < 0:
        return None
    rho = max(0.85 * fc / fy * (1 - math.sqrt(q)), 1.4 / fy)
    return rho * 1000 * d * 1000


def phi_vc(d, fc):
    """Resistencia a cortante φVc (kN/m), NSR-10 C.11."""
    return 0.75 * 0.17 * math.sqrt(fc) * d * 1000


def bar(As):
    """Devuelve (texto, separación en m) para el área As en mm2/m."""
    if not As or As <= 0:
        return "Insuficiente: aumentar espesor", None
    for nombre, area in BARS:
        s = area / As * 1000
        if s >= 100:
            s = min(300, math.floor(s / 25) * 25)
            return f"{nombre} @ {s / 1000:.2f} m", s / 1000
    return "Revisar (#7 @ 0.10 m insuficiente)", None


def p_suelo(z, K, gs, nf, qs):
    """Presión horizontal (kPa) de suelo + agua freática + sobrecarga a profundidad z."""
    sub = max(0.0, z - nf)
    return K * (gs * min(z, nf) + (gs - GW) * sub + qs) + GW * sub


# ------------------------------------------------------------------- cálculo
def disenar(d: Datos):
    ent, cer = d.enterrado, d.cerrado
    V, H, r, fc, fy, gs, qs = d.V, d.H, d.r, d.fc, d.fy, d.gs, d.qs
    nf = math.inf if d.nf is None else d.nf
    Hc = d.Hc if (ent and cer) else 0.0
    B = math.sqrt(V / (H * r))
    L = B * r
    Ka = math.tan(math.radians(45 - d.phi / 2)) ** 2
    K0 = 1 - math.sin(math.radians(d.phi))
    K = K0 if cer else Ka
    z0, z1 = Hc, Hc + H

    # ---- Muro (franja vertical de 1 m, igual para los 4 muros)
    e_min = max(0.20, math.ceil(H / 12 * 20) / 20)
    manual_m = d.eM is not None
    e = d.eM if manual_m else e_min
    W = None
    while e <= 1.0 + 1e-9:
        dd = e - 0.05 - 0.008
        w0 = GW * H                                   # caso A: tanque lleno
        if cer:
            MA, VA, MpA = w0 * H * H / 15, 0.4 * w0 * H, w0 * H * H / 33.6
        else:
            MA, VA, MpA = w0 * H * H / 6, w0 * H / 2, 0.0
        MB = VB = MpB = p0 = p1 = 0.0                 # caso B: vacío + suelo/freático
        if ent:
            p0, p1 = p_suelo(z0, K, gs, nf, qs), p_suelo(z1, K, gs, nf, qs)
            if cer:
                MB = p0 * H * H / 8 + (p1 - p0) * H * H / 15
                VB = 0.625 * p0 * H + 0.4 * (p1 - p0) * H
                MpB = p0 * H * H / 14.2 + (p1 - p0) * H * H / 33.6
            else:
                MB = p0 * H * H / 2 + (p1 - p0) * H * H / 6
                VB = p0 * H + (p1 - p0) * H / 2
        Mu = max(1.4 * MA * SD, 1.6 * MB * SD)
        Vu = max(1.4 * VA, 1.6 * VB)
        MuP = max(1.4 * MpA * SD, 1.6 * MpB * SD)
        As = as_req(Mu, dd, fc, fy)
        AsP = as_req(max(MuP, 0.01), dd, fc, fy)
        ok = As is not None and Vu <= phi_vc(dd, fc)
        if manual_m or ok:
            W = dict(ok=ok, e=e, d=dd, MA=MA, MB=MB, Mu=Mu, Vu=Vu, As=As, AsP=AsP,
                     p0=p0, p1=p1, gov="tanque lleno" if 1.4 * MA >= 1.6 * MB
                     else "tanque vacío (suelo + freático)")
            break
        e = round(e + 0.05, 4)
    if W is None:
        raise ValueError("No se logró un espesor de muro ≤ 1.00 m. Revise los datos.")
    e = W["e"]
    Ah = 0.003 * e * 1e6 / 2        # acero horizontal por cara (mm2/m)

    # ---- Tapa
    hr, R = 0.0, None
    if cer:
        qv = qs if ent else 1.0
        manual_t = d.eT is not None
        hr = d.eT if manual_t else max(0.15, math.ceil(B / 20 * 20) / 20)
        while hr <= 0.6 + 1e-9:
            dd = hr - 0.04 - 0.008
            wu = 1.2 * (GC * hr + gs * Hc) + 1.6 * qv
            M, Vu = wu * B * B / 8 * SD, wu * B / 2
            As = as_req(M, dd, fc, fy)
            ok = As is not None and Vu <= phi_vc(dd, fc)
            if manual_t or ok:
                R = dict(ok=ok, wu=wu, M=M, Vu=Vu, As=As, d=dd)
                break
            hr = round(hr + 0.05, 4)

    # ---- Pesos y losa de fondo
    Lx, Bx = L + 2 * e, B + 2 * e
    Ab = Lx * Bx
    top = hr if cer else 0.0
    Wmuros = GC * (Ab - L * B) * H
    Wtapa = GC * Ab * hr if cer else 0.0
    Wsuelo = gs * Hc * Ab if cer else 0.0
    Wagua = GW * L * B * H

    manual_f = d.eF is not None
    ef = d.eF if manual_f else max(e, 0.20)
    F, Hu = None, 0.0
    while ef <= 1.0 + 1e-9:
        Hu = max(0.0, Hc + H + ef - nf)
        wnet = max(0.0, GW * Hu - GC * ef)
        dd = ef - 0.075 - 0.008
        M = max(wnet * B * B / 12 * 1.4 * SD, 0.01)
        Vu = 1.4 * wnet * B / 2
        As = as_req(M, dd, fc, fy)
        ok = As is not None and Vu <= phi_vc(dd, fc)
        if manual_f or ok:
            F = dict(ok=ok, d=dd, M=M, Vu=Vu, As=As)
            break
        ef = round(ef + 0.05, 4)
    if F is None:
        ef = 1.0

    vo = max(0.0, d.vo)
    Ab2 = (Lx + 2 * vo) * (Bx + 2 * vo)
    hs = Hc + top + H
    suelo_vo = (gs * min(hs, nf) + (gs - GW) * max(0.0, hs - nf)) if ent else 0.0
    Wvo = (Ab2 - Ab) * (GC * ef + suelo_vo)
    Wbase = GC * Ab * ef
    Wvacio = Wmuros + Wtapa + Wsuelo + Wbase + Wvo
    U = GW * Hu * Ab2
    Fs = Wvacio / U if U > 0 else None
    Wtot = Wvacio + Wagua
    qnet = (Wtot - GW * Hu * Ab2) / Ab2 if (ent and Hu > 0) else Wtot / Ab2

    # ---- Sismo (Housner simplificado)
    Sa = 2.5 * d.Aa * d.Fa * d.I
    lam = 0.866 * L / H
    Wi = Wagua * math.tanh(lam) / lam
    Vs = Sa * (Wi + Wmuros + Wtapa) / 2.0
    mu = math.tan(math.radians(2 / 3 * d.phi))
    fsd = mu * Wtot / Vs

    # ---- Armado
    bv, _ = bar(W["As"])
    bvp, _ = bar(W["AsP"]) if cer else ("", None)
    bh, sh = bar(Ah)
    bf, sf = bar(max(F["As"] if F else 0, 0.0033 * 1000 * (ef - 0.083) * 1000))
    br, sr = bar(R["As"]) if (cer and R) else ("", None)

    mal = lambda t: t.startswith(("Insuficiente", "Revisar"))
    checks = [
        ("Muro: flexión y cortante (C.10, C.11)", W["ok"] and not mal(bv), f"e = {e:.2f} m"),
        ("Muro: espesor mínimo (≥ H/12 y ≥ 0.20 m)", e >= e_min - 1e-9, f"mínimo {e_min:.2f} m"),
    ]
    if cer:
        checks += [
            ("Tapa: flexión y cortante", bool(R and R["ok"]), f"h = {hr:.2f} m"),
            ("Tapa: espesor mínimo (h ≥ B/20, C.9.5.2.1)", hr >= B / 20 - 1e-9, f"mínimo {B / 20:.2f} m"),
        ]
    checks += [
        ("Losa de fondo: flexión y cortante", bool(F and F["ok"]), f"ef = {ef:.2f} m"),
        ("Flotación (Fs ≥ 1.10)", Fs is None or Fs >= 1.1, "No aplica" if Fs is None else f"Fs = {Fs:.2f}"),
        ("Capacidad portante", qnet <= d.qa, f"{qnet:.1f} / {d.qa:.0f} kPa"),
    ]
    if not ent:
        checks.append(("Deslizamiento (FS ≥ 1.5)", fsd >= 1.5, f"FS = {fsd:.2f}"))

    return dict(d=d, ent=ent, cer=cer, L=L, B=B, H=H, e=e, ef=ef, hr=hr, Hc=Hc, nf=nf,
                vo=vo, Ka=Ka, K0=K0, K=K, W=W, R=R, F=F, Ah=Ah, bv=bv, bvp=bvp, bh=bh,
                bf=bf, br=br, sh=sh, sf=sf, sr=sr, U=U, Fs=Fs, Wvacio=Wvacio, Hu=Hu,
                qnet=qnet, Sa=Sa, Wi=Wi, Wagua=Wagua, Vs=Vs, fsd=fsd, checks=checks,
                e_min=e_min, pa=GW * H)


def auto_ajustar(d: Datos, max_iter=16):
    """Modifica espesores / voladizo hasta cumplir; devuelve (datos, resultado, mensaje)."""
    msg = ("No fue posible cumplir todo solo con estos ajustes: modifique volumen, altura "
           "o relación L/B, o mejore el suelo de fundación.")
    res = disenar(d)
    for i in range(max_iter):
        fallas = [c[0] for c in res["checks"] if not c[1]]
        if not fallas:
            msg = ("Se ajustaron las dimensiones hasta cumplir todas las verificaciones."
                   if i else "Ya cumple todas las verificaciones.")
            break
        tiene = lambda k: any(t.startswith(k) for t in fallas)
        cambio = False
        if (tiene("Muro") or tiene("Tapa") or tiene("Losa")) and \
                any(x is not None for x in (d.eM, d.eT, d.eF)):
            d = replace(d, eM=None, eT=None, eF=None)
            cambio = True
        if not cambio and (tiene("Flotación") or tiene("Capacidad")) and d.vo < 3:
            d = replace(d, vo=d.vo + 0.25)
            cambio = True
        if not cambio and tiene("Deslizamiento") and res["ef"] < 1:
            d = replace(d, eF=round(res["ef"] + 0.05, 2))
            cambio = True
        if not cambio:
            break
        res = disenar(d)
    return d, res, msg


# ------------------------------------------------------------------- reporte
def reporte(x):
    f = lambda v, n=2: f"{v:.{n}f}"
    W, R, F = x["W"], x["R"], x["F"]
    ent, cer, d = x["ent"], x["cer"], x["d"]
    L = []
    add = L.append
    add("=" * 70)
    add("DISEÑO ESTRUCTURAL PRELIMINAR DE TANQUE (NSR-10 / ACI 350)")
    add("=" * 70)
    add(f"Tipo: {'enterrado' if ent else 'superficial'} / {'cerrado' if cer else 'abierto'}"
        f" | Nivel freático: {'no existe' if d.nf is None else f(d.nf) + ' m'}")
    add("\n-- VERIFICACIÓN NORMATIVA --")
    for n, ok, det in x["checks"]:
        add(f"  [{'CUMPLE' if ok else 'NO CUMPLE':9}] {n:48} {det}")
    add("\n-- GEOMETRÍA --")
    add(f"  Interior L x B x H = {f(x['L'])} x {f(x['B'])} x {f(x['H'])} m  (V = {f(x['L']*x['B']*x['H'],1)} m3)")
    add(f"  Ka = {f(x['Ka'],3)} | K0 = {f(x['K0'],3)} | se usa K = {f(x['K'],3)} "
        f"({'reposo' if cer else 'activo'})")
    add("\n-- MUROS (franja vertical de 1 m, válida para los 4 muros) --")
    add(f"  Espesor: {f(x['e'])} m | apoyo: "
        f"{'empotrado en base, articulado en tapa' if cer else 'voladizo empotrado en base'}")
    add(f"  Presión del agua en la base (lleno): {f(x['pa'],1)} kPa")
    if ent:
        add(f"  Presión suelo+freático+sobrecarga tope/base: {f(W['p0'],1)} / {f(W['p1'],1)} kPa")
        if x["nf"] < math.inf:
            add(f"  Suelo seco hasta {f(x['nf'])} m; sumergido (γ' = {f(d.gs-GW,1)} kN/m3) por debajo")
    add(f"  Caso crítico: {W['gov']} | Mu = {f(W['Mu'],1)} kN·m/m")
    add(f"  Vu / φVc = {f(W['Vu'],1)} / {f(phi_vc(W['d'], d.fc),1)} kN/m")
    add(f"  Acero vertical (base): {x['bv']}" + (f" | vano: {x['bvp']}" if cer else ""))
    add(f"  Acero horizontal: {x['bh']} por cara (ρ = 0.003) | recubrimiento 5 cm")
    if cer and R:
        add("\n-- TAPA --")
        add(f"  Espesor {f(x['hr'])} m | wu = {f(R['wu'],1)} kN/m2 | Mu = {f(R['M'],1)} kN·m/m")
        add(f"  Acero principal: {x['br']} ambas caras | repartición ρ = 0.0018")
    add("\n-- LOSA DE FONDO, ESTABILIDAD Y SUELO --")
    add(f"  Espesor {f(x['ef'])} m | voladizo {f(x['vo'])} m | acero: {x['bf']} (ambas direcciones y caras)")
    add(f"  Subpresión (vacío): {f(x['U'],1)} kN (columna de agua {f(x['Hu'])} m) | "
        f"peso resistente {f(x['Wvacio'],1)} kN")
    add(f"  Presión sobre el suelo (lleno): {f(x['qnet'],1)} kPa (admisible {f(d.qa,0)} kPa)")
    add("\n-- SISMO --")
    add(f"  Sa = 2.5·Aa·Fa·I = {f(x['Sa'],3)} g | masa impulsiva Wi = {f(x['Wi'],0)} kN")
    if ent:
        add("  Enterrado: verificar empuje sísmico del suelo (Mononobe-Okabe, NSR-10 Título H).")
    else:
        add(f"  Cortante basal V = {f(x['Vs'],0)} kN (R = 2.0) | deslizamiento FS = {f(x['fsd'])}")
    add("\n-- ALCANCES --")
    add("  Preliminar. No incluye: tensión directa horizontal en muros, control de fisuración,")
    add("  presión sísmica del suelo, sloshing completo, juntas ni longitudes de desarrollo (C.12).")
    add("  Factores: 1.4 fluido, 1.6 suelo, 1.2D+1.6L tapa, Sd = 1.3 en flexión (ACI 350).")
    add("  Debe ser revisado y firmado por ingeniero con matrícula profesional (Ley 400/1997).")
    return "\n".join(L)


# ------------------------------------------------------------------ gráficos
def graficar(x, archivo="tanque_esquemas.png", mostrar=True):
    import matplotlib
    if not mostrar:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Polygon

    ent, cer, d = x["ent"], x["cer"], x["d"]
    L, B, H, e, ef, hr, Hc, nf, vo = (x[k] for k in ("L", "B", "H", "e", "ef", "hr", "Hc", "nf", "vo"))
    Lx, Bx = L + 2 * e, B + 2 * e
    top = hr if cer else 0.0
    cov = Hc if ent else 0.0
    yT = cov
    yI, yB0 = yT + top, yT + top + H
    yB = yB0 + ef
    c = 0.05
    fig, ax = plt.subplots(1, 3, figsize=(19, 6.5), gridspec_kw={"width_ratios": [1.1, 1.1, 1]})

    # --- 1. Corte A-A
    a = ax[0]
    a.set_title("Corte A-A (cruza los muros cortos)")
    if ent:
        a.add_patch(Rectangle((-1.2, 0), Lx + 2.4, yB + 0.4, fill=False, hatch="///", ec="#999"))
        if nf < yB + 0.4:
            a.add_patch(Rectangle((-1.2, nf), Lx + 2.4, yB + 0.4 - nf, color="#3a9bc4", alpha=0.25))
            a.axhline(nf, color="#2b7fd0", ls="--")
            a.text(-1.15, nf - 0.1, f"N.F. a {nf:.2f} m", color="#2b7fd0", fontsize=9)
        a.axhline(0, color="k", lw=2)
        a.text(-1.15, -0.15, "Superficie del terreno", fontsize=9)
    else:
        a.add_patch(Rectangle((-1.2, yB), Lx + 2.4, 0.4, fill=False, hatch="///", ec="#999"))
        a.axhline(yB, color="k", lw=2)
    a.add_patch(Rectangle((0, yT), Lx, yB - yT, color="#b9c3c7"))
    if vo > 0:
        a.add_patch(Rectangle((-vo, yB0), Lx + 2 * vo, ef, color="#b9c3c7"))
    a.add_patch(Rectangle((e, yI), L, H, color="white"))
    a.add_patch(Rectangle((e, yI), L, H, color="#3a9bc4", alpha=0.35))
    a.text(Lx / 2, (yI + yB0) / 2, "Agua", ha="center")
    rojo = dict(color="#b3261e", lw=2)
    h = 0.5
    for xi, xo, sg in ((e - c, c, 1), (Lx - e + c, Lx - c, -1)):
        a.plot([xi, xi, xi + sg * h], [yT + c, yB - c, yB - c], **rojo)
        a.plot([xo, xo, xo + sg * h], [yT + c, yB0 + c, yB0 + c], **rojo)
        if x["sh"]:
            ys = [yI + x["sh"] / 2 + i * x["sh"] for i in range(int(H / x["sh"]))]
            a.scatter([xi] * len(ys), ys, s=8, color="#b3261e")
            a.scatter([xo] * len(ys), ys, s=8, color="#b3261e")
    mats = [(yB0 + c, x["sf"]), (yB - c, x["sf"])] + ([(yT + c, x["sr"]), (yI - c, x["sr"])] if cer else [])
    for yy, s in mats:
        a.plot([c, Lx - c], [yy, yy], **rojo)
        if s:
            xs = [c + s / 2 + i * s for i in range(int((Lx - 2 * c) / s))]
            a.scatter(xs, [yy] * len(xs), s=7, color="#b3261e")
    a.text(Lx + 0.2, yT + 0.3, f"H = {H:.2f}\ne = {e:.2f}\nef = {ef:.2f}" + (f"\nhr = {hr:.2f}" if cer else ""), fontsize=9)
    a.set_xlim(-1.3 - vo, Lx + 1.9)
    a.set_aspect("equal")
    a.invert_yaxis()

    # --- 2. Presiones sobre un muro (A: derecha, B: izquierda)
    p = ax[1]
    p.set_title("Presiones sobre el muro (franja de 1 m)")
    z0, z1 = cov, cov + H
    kk = K = x["K"]
    pe = lambda z: K * (d.gs * min(z, nf) + (d.gs - GW) * max(0, z - nf) + d.qs)
    wf = lambda z: GW * max(0, z - nf)
    pa = x["pa"]
    pb = pe(z1) + wf(z1) if ent else 0
    esc = 1.0 / max(pa, pb, 1)
    p.add_patch(Rectangle((-0.03, z0 - 0.2), 0.06, H + 0.4, color="#b9c3c7"))
    p.add_patch(Polygon([(0.03, z0), (0.03 + pa * esc, z1), (0.03, z1)], color="#3a9bc4", alpha=0.4))
    p.text(0.05 + pa * esc, z1, f"A (lleno): {pa:.1f} kPa", va="bottom", fontsize=9)
    if ent:
        zs = [z0] + ([nf] if z0 < nf < z1 else []) + [z1]
        for za, zb in zip(zs[:-1], zs[1:]):
            sub = (za + zb) / 2 > nf
            p.add_patch(Polygon([(-0.03, za), (-0.03 - pe(za) * esc, za), (-0.03 - pe(zb) * esc, zb), (-0.03, zb)],
                                color="#7a5c3e" if sub else "#d9a441", alpha=0.55))
            p.add_patch(Polygon([(-0.03 - pe(za) * esc, za), (-0.03 - (pe(za) + wf(za)) * esc, za),
                                 (-0.03 - (pe(zb) + wf(zb)) * esc, zb), (-0.03 - pe(zb) * esc, zb)],
                                color="#3a9bc4", alpha=0.4))
        if z0 < nf < z1:
            p.axhline(nf, color="#2b7fd0", ls="--", lw=1)
        pt = pe(z0) + wf(z0)
        p.text(-0.05 - pb * esc, z1 + 0.1, f"B (vacío): tope {pt:.1f} / base {pb:.1f} kPa", fontsize=9, ha="left")
        p.text(-0.05 - pb * esc, z1 + 0.35, "ámbar: suelo seco | marrón: suelo sumergido | azul: agua", fontsize=8)
    p.set_xlim(-1.25, 1.25)
    p.set_ylim(z1 + 0.6, z0 - 0.4)
    p.set_xticks([])

    # --- 3. Planta
    q = ax[2]
    q.set_title("Planta: malla de fondo y aros de muros")
    q.add_patch(Rectangle((0, 0), Lx, Bx, color="#b9c3c7"))
    q.add_patch(Rectangle((e, e), L, B, color="white"))
    if x["sf"]:
        s = x["sf"]
        for xx in [e + s / 2 + i * s for i in range(int(L / s))]:
            q.plot([xx, xx], [e, Bx - e], color="#b3261e", lw=0.7)
        for yy in [e + s / 2 + i * s for i in range(int(B / s))]:
            q.plot([e, Lx - e], [yy, yy], color="#b3261e", lw=0.7)
    q.add_patch(Rectangle((c, c), Lx - 2 * c, Bx - 2 * c, fill=False, ec="#b3261e", lw=1.5))
    q.add_patch(Rectangle((e - c, e - c), L + 2 * c, B + 2 * c, fill=False, ec="#b3261e", lw=1.5))
    q.axhline(Bx / 2, color="k", ls="--", lw=1)
    q.text(-0.1, Bx / 2, "A", ha="right", va="center")
    q.text(Lx + 0.1, Bx / 2, "A", va="center")
    q.add_patch(Rectangle((0, Bx / 2 - 0.5), e, 1, color="#0b6e6e"))
    q.add_patch(Rectangle((Lx / 2 - 0.5, 0), 1, e, color="#0b6e6e"))
    q.text(Lx / 2, -0.35, f"{Lx:.2f} x {Bx:.2f} m (exterior) | franjas de 1 m en color", ha="center", fontsize=9)
    q.set_aspect("equal")
    q.set_xlim(-0.8, Lx + 0.8)
    q.set_ylim(Bx + 0.4, -0.8)

    fig.suptitle(f"Acero: muro vert. {x['bv']} | muro horiz. {x['bh']}/cara | fondo {x['bf']}"
                 + (f" | tapa {x['br']}" if cer else ""), fontsize=10)
    fig.tight_layout()
    if archivo:
        fig.savefig(archivo, dpi=130)
        print(f"Esquemas guardados en {archivo}")
    if mostrar:
        plt.show()


# ------------------------------------------------------------------ interfaz
def preguntar(texto, defecto, tipo=float):
    r = input(f"{texto} [{defecto}]: ").strip()
    return tipo(r) if r else defecto


def si_no(texto, opciones, defecto):
    r = input(f"{texto} ({'/'.join(opciones)}) [{defecto}]: ").strip().lower()
    return r if r in opciones else defecto


def datos_interactivos():
    d = Datos()
    d.enterrado = si_no("Tanque", ("enterrado", "superficial"), "enterrado") == "enterrado"
    d.cerrado = si_no("Cubierta", ("cerrado", "abierto"), "cerrado") == "cerrado"
    nf = input("Nivel freático, profundidad desde la superficie en m (Enter = no existe): ").strip()
    d.nf = float(nf) if nf else None
    d.V = preguntar("Volumen útil (m3)", d.V)
    d.H = preguntar("Altura de agua (m)", d.H)
    d.r = preguntar("Relación largo/ancho", d.r)
    if d.enterrado and d.cerrado:
        d.Hc = preguntar("Tierra sobre la tapa (m)", d.Hc)
    d.qs = preguntar("Sobrecarga (kN/m2)", d.qs)
    d.fc = preguntar("f'c (MPa)", d.fc)
    d.fy = preguntar("fy (MPa)", d.fy)
    d.gs = preguntar("Peso unitario del suelo (kN/m3)", d.gs)
    d.phi = preguntar("Ángulo de fricción (°)", d.phi)
    d.qa = preguntar("Capacidad portante admisible (kPa)", d.qa)
    d.Aa = preguntar("Aa", d.Aa)
    d.Fa = preguntar("Fa", d.Fa)
    d.I = preguntar("Coeficiente de importancia I (1.5 / 1.25 / 1.1)", d.I)
    return d


def main():
    ap = argparse.ArgumentParser(description="Diseño preliminar de tanques (NSR-10)")
    ap.add_argument("--demo", action="store_true", help="usa los datos por defecto")
    ap.add_argument("--auto", action="store_true", help="ajusta dimensiones hasta cumplir")
    ap.add_argument("--graficos", action="store_true", help="genera los esquemas (matplotlib)")
    ap.add_argument("--sin-ventana", action="store_true", help="solo guarda la imagen, no la muestra")
    a = ap.parse_args()

    d = Datos() if a.demo else datos_interactivos()
    if a.auto:
        d, x, msg = auto_ajustar(d)
        print(msg)
    else:
        x = disenar(d)
    print(reporte(x))
    if a.graficos:
        graficar(x, mostrar=not a.sin_ventana)


if __name__ == "__main__":
    main()
