import olefile, zlib, struct, sys
f = olefile.OleFileIO(sys.argv[1])
hdr = f.openstream('FileHeader').read()
compressed = bool(struct.unpack('<I', hdr[36:40])[0] & 1)
data = f.openstream('BodyText/Section0').read()
if compressed:
    data = zlib.decompress(data, -15)
PARA_TEXT = 0x10 + 51
EXT = {1,2,3,11,12,14,15,16,17,18,21,22,23}
INLINE = {4,5,6,7,8,9,19,20}
out = []
pos = 0
while pos < len(data):
    h = struct.unpack('<I', data[pos:pos+4])[0]
    tag = h & 0x3FF
    size = (h >> 20) & 0xFFF
    pos += 4
    if size == 0xFFF:
        size = struct.unpack('<I', data[pos:pos+4])[0]
        pos += 4
    body = data[pos:pos+size]
    pos += size
    if tag == PARA_TEXT:
        s = []
        i = 0
        while i + 1 < len(body):
            c = struct.unpack('<H', body[i:i+2])[0]
            if c in EXT or c in INLINE:
                i += 16
                if c == 9: s.append('\t')
                continue
            if c == 13: s.append('\n')
            elif c >= 32 or c == 10: s.append(chr(c))
            i += 2
        out.append(''.join(s))
print('\n'.join(out))
