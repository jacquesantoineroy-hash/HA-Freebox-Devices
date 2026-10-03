"""Réduit une capture PNG (RGBA 8 bits) d'un facteur entier, sans PIL : python3 mini_png.py entree.png sortie.png 4"""
import base64
import struct
import sys
import zlib


def lire(chemin):
    data = open(chemin, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    largeur = hauteur = 0
    idat = b""
    canaux = 4
    while pos < len(data):
        (taille,) = struct.unpack(">I", data[pos:pos + 4])
        genre = data[pos + 4:pos + 8]
        corps = data[pos + 8:pos + 8 + taille]
        if genre == b"IHDR":
            largeur, hauteur, bits, couleur = struct.unpack(">IIBB", corps[:10])
            canaux = {6: 4, 2: 3, 0: 1}[couleur]
            assert bits == 8
        elif genre == b"IDAT":
            idat += corps
        pos += 12 + taille
    brut = zlib.decompress(idat)
    ligne = largeur * canaux
    lignes = []
    prec = bytearray(ligne)
    i = 0
    for _ in range(hauteur):
        f = brut[i]
        cur = bytearray(brut[i + 1:i + 1 + ligne])
        i += 1 + ligne
        if f == 1:
            for x in range(canaux, ligne):
                cur[x] = (cur[x] + cur[x - canaux]) & 255
        elif f == 2:
            for x in range(ligne):
                cur[x] = (cur[x] + prec[x]) & 255
        elif f == 3:
            for x in range(ligne):
                g = cur[x - canaux] if x >= canaux else 0
                cur[x] = (cur[x] + ((g + prec[x]) >> 1)) & 255
        elif f == 4:
            for x in range(ligne):
                a = cur[x - canaux] if x >= canaux else 0
                b = prec[x]
                c = prec[x - canaux] if x >= canaux else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else b if pb <= pc else c
                cur[x] = (cur[x] + pr) & 255
        lignes.append(cur)
        prec = cur
    return largeur, hauteur, canaux, lignes


def ecrire(chemin, largeur, hauteur, lignes):
    def bloc(genre, corps):
        return struct.pack(">I", len(corps)) + genre + corps + struct.pack(">I", zlib.crc32(genre + corps) & 0xFFFFFFFF)
    brut = b"".join(b"\x00" + bytes(l) for l in lignes)
    png = b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0))
    png += bloc(b"IDAT", zlib.compress(brut, 9)) + bloc(b"IEND", b"")
    open(chemin, "wb").write(png)


def reduire(entree, sortie, facteur):
    largeur, hauteur, canaux, lignes = lire(entree)
    nl, nh = largeur // facteur, hauteur // facteur
    out = []
    for y in range(nh):
        rangee = bytearray(nl * 3)
        for x in range(nl):
            r = g = b = 0
            for dy in range(facteur):
                src = lignes[y * facteur + dy]
                for dx in range(facteur):
                    o = (x * facteur + dx) * canaux
                    r += src[o]; g += src[o + 1]; b += src[o + 2]
            n = facteur * facteur
            rangee[x * 3] = r // n; rangee[x * 3 + 1] = g // n; rangee[x * 3 + 2] = b // n
        out.append(rangee)
    ecrire(sortie, nl, nh, out)
    return nl, nh


if __name__ == "__main__":
    nl, nh = reduire(sys.argv[1], sys.argv[2], int(sys.argv[3]))
    if len(sys.argv) > 4:
        open(sys.argv[4], "w").write(base64.b64encode(open(sys.argv[2], "rb").read()).decode())
    print(nl, nh)
