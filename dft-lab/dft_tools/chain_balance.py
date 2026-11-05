"""链分配：先均衡长度，再在每条链内按负沿、正沿和测试时钟域排序。

输入为实际 FF 清单；输出按 SI→SO 顺序的链。Lock-up latch 不计入 scan 位数。
★ 本例四条链只是管脚/测试时间的教学选择，不是工业推荐的固定数字。
物理设计重排必须保持时钟/边沿边界，并重导出映射和 ATPG pattern。
"""


def balance(registers, count):
    if not 1 <= count <= len(registers):
        raise ValueError('链数必须在 1 与寄存器总数之间')
    chains = [[] for _ in range(count)]
    # 分别摊开各类寄存器，避免四个负沿单元集中在同一条链。
    ordered = sorted(registers, key=lambda r: (r['edge'] != 'negative', r['clock_domain'], r['name']))
    for register in ordered:
        chain = min(chains, key=len)
        chain.append(register)
    for index, chain in enumerate(chains):
        chain.sort(key=lambda r: (r['edge'] != 'negative', r['clock_domain'] == 'aux', r['name']))
        for position, register in enumerate(chain):
            register['chain'] = index
            register['position'] = position
    return chains
