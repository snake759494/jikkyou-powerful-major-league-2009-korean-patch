"""팩 안 0x8000xxxx 포인터(파일오프셋|0x80000000) 분석."""
import numpy as np, struct
def pointers(b):
    """(포인터 위치, 대상 오프셋) 목록. 4바이트 정렬."""
    a = np.frombuffer(b[:len(b) // 4 * 4], '<u4')
    idx = np.nonzero(((a >> 24) == 0x80) & ((a & 0xffffff) < len(b)) & ((a & 0xffffff) > 0))[0]
    return [(int(i) * 4, int(a[i]) & 0xffffff) for i in idx]
