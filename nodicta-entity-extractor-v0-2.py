import sys
import re
from collections import Counter
from collections import defaultdict
import time
from itertools import groupby

# ---------- 分章节 ----------
def split_chapters(text):
    title_pattern = re.compile(r'^第[0-9一二三四五六七八九十百千零]+[章回]')
    chapters = []
    current_title = None
    current_lines = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_title is not None:
                current_lines.append('')
            continue
        if title_pattern.match(line):
            if current_title is not None:
                content = '\n'.join(current_lines)
                content = re.sub(r'\n\s*\n+', '\n\n', content).strip()
                chapters.append((current_title, content))
            current_title = line
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(line)

    if current_title is not None:
        content = '\n'.join(current_lines)
        content = re.sub(r'\n\s*\n+', '\n\n', content).strip()
        chapters.append((current_title, content))

    return chapters


# ---------- 中文字符判断 ----------
def is_chinese_char(ch):
    code = ord(ch)
    return (
        0x3400 <= code <= 0x4DBF or
        0x4E00 <= code <= 0x9FFF or
        0x30000 <= code <= 0x323AF
    )


# ---------- 数据容器 ----------
class UnitInfo:
    def __init__(self, text, chapter_idx=None, paragraph_idx=None,
                 line_idx=None, sentence_idx=None, clause_idx=None):
        self.text = text
        self.chapter_idx = chapter_idx
        self.paragraph_idx = paragraph_idx
        self.line_idx = line_idx
        self.sentence_idx = sentence_idx
        self.clause_idx = clause_idx

        self.char_freq = Counter(ch for ch in text if is_chinese_char(ch))
        self.total_chars = sum(self.char_freq.values())
        self.unique_count = len(self.char_freq)
        
        # 懒加载
        self._char_freq_list = None

    @property
    def char_freq_list(self):
        if self._char_freq_list is None:
            self._char_freq_list = self.char_freq.most_common()
        return self._char_freq_list


# ---------- 生成指定粒度的单元迭代器 ----------
def iter_units(chapters, unit):
    unit = unit.lower()
    if unit == 'full':
        full_text = '\n'.join(title + '\n' + content for title, content in chapters)
        yield UnitInfo(full_text)
    elif unit == 'chapter':
        for i, (title, content) in enumerate(chapters, 1):
            text = title + '\n' + content
            yield UnitInfo(text, chapter_idx=i)
    else:
        for ch_idx, (title, content) in enumerate(chapters, 1):
            paragraphs = content.split('\n\n')
            for p_idx, paragraph in enumerate(paragraphs, 1):
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                if unit == 'paragraph':
                    yield UnitInfo(paragraph, chapter_idx=ch_idx, paragraph_idx=p_idx)
                else:
                    lines = [line.strip() for line in paragraph.split('\n') if line.strip()]
                    for l_idx, line in enumerate(lines, 1):
                        if unit == 'line':
                            yield UnitInfo(line, chapter_idx=ch_idx, paragraph_idx=p_idx, line_idx=l_idx)
                        else:
                            line = re.sub(r'["“”]', '', line)
                            sentences = re.split(r'[。！？；!?;…~～—.\-]+', line)
                            sentences = [s.strip() for s in sentences if s.strip()]
                            for s_idx, sentence in enumerate(sentences, 1):
                                if unit == 'sentence':
                                    yield UnitInfo(sentence, chapter_idx=ch_idx, paragraph_idx=p_idx, line_idx=l_idx, sentence_idx=s_idx)
                                else:  # clause
                                    clauses = re.split(r'[，,；;：:、/]+', sentence)
                                    clauses = ["".join(c.split()) for c in clauses if c.strip()]
                                    for c_idx, clause in enumerate(clauses, 1):
                                        yield UnitInfo(clause,
                                                       chapter_idx=ch_idx,
                                                       paragraph_idx=p_idx,
                                                       line_idx=l_idx,
                                                       sentence_idx=s_idx,
                                                       clause_idx=c_idx)

# ---------- 打印常规统计 ----------
def print_stats(chapters, unit='paragraph', max_freq_print=20):
    unit_names = {
        'full': '全文',
        'chapter': '章节',
        'paragraph': '段落',
        'line': '行',
        'sentence': '句子',
        'clause': '半句'
    }
    if unit in ('clause'):
        unit = 'clause'
    elif unit == 'all':
        for u in ['full', 'chapter', 'paragraph', 'line', 'sentence', 'clause']:
            print_stats(chapters, u, max_freq_print)
            print()
        return

    unit_label = unit_names.get(unit, unit)
    units = list(iter_units(chapters, unit))

    total_counter = Counter()
    for info in units:
        total_counter.update(info.char_freq)

    print(f"统计粒度：{unit_label}")
    for idx, info in enumerate(units):
        pos_parts = []
        if info.chapter_idx is not None:
            pos_parts.append(f"第{info.chapter_idx}章")
        if info.paragraph_idx is not None:
            pos_parts.append(f"第{info.paragraph_idx}段")
        if info.line_idx is not None:
            pos_parts.append(f"第{info.line_idx}行")
        if info.sentence_idx is not None:
            pos_parts.append(f"第{info.sentence_idx}句")
        if info.clause_idx is not None:
            pos_parts.append(f"第{info.clause_idx}个半句")
        position = "、".join(pos_parts) if pos_parts else "全文"

        print(f"index {idx}: [{position}] 中文字符总数={info.total_chars}, 唯一字符个数={info.unique_count}")
        freq_list = info.char_freq_list
        if freq_list:
            show_list = freq_list[:max_freq_print]
            print(f"  唯一字符频率列表: {show_list}")
            if len(freq_list) > max_freq_print:
                print(f"  （共 {len(freq_list)} 个唯一字符，仅显示前 {max_freq_print} 个）")
        else:
            print("  唯一字符频率列表: []")

    total_freq_list = total_counter.most_common()
    print(f"\n所有单元合并唯一字符频率列表（共 {len(total_freq_list)} 个唯一字符，显示前 {max_freq_print} 个）:")
    print(total_freq_list[:max_freq_print])
    if len(total_freq_list) > max_freq_print:
        print(f"（其余 {len(total_freq_list) - max_freq_print} 个未显示）")

    return units, total_freq_list


# ---------- 高频字符语境分析与关联字符挖掘 ----------
def analyze_chars(all_clause_units, top_n=None, max_freq_print=20, print_analyze_chars_process=False):
    """
    参数：
        top_n: 若指定，则只分析前 top_n 个最高频字符；若为 None，则分析所有字符。
        max_freq_print: 打印左右频率列表时最多显示的条目数。
        print_analyze_chars_process: 打印完整分析过程。

    逻辑：
        - 对于每个目标字符，找到包含它的所有半句，按该字符切分为左右两部分。
        - 在统计左右部分字符频率时，会先过滤掉已标记为非关键字符的字符
          （这些字符在之前的循环中被判定为非关键，后续不再参与计算）。
        - 然后对左右频率列表执行 while 循环，找出关键字符：
            * 频率与目标字符总频率的比值 > 0.5，或
            * 该字符在当前部分出现的次数占其全文总出现次数的比例 > 0.8
        - 若左右均无关键字符，则将目标字符加入非关键字符列表，
          之后循环遇到该字符时，会从左右频率列表中直接忽略。
        - 所有被判定为关键字符的关联字符，都会同时打印并记录其：
            * 半句内占比：当前部分频率 / 目标字符总频次
            * 全文占比：当前部分频率 / 该字符全文总频次
    """

    total_counter = Counter()
    char_to_clauses = defaultdict(list)      # 字符 → 包含它的 clause 列表

    for clause in all_clause_units:
        total_counter.update(clause.char_freq)
        for ch in clause.char_freq:
            char_to_clauses[ch].append(clause)

    top_chars = total_counter.most_common(top_n)

    if top_n is not None:
        if print_analyze_chars_process:
            print(f"=== 前 {top_n} 个最高频字符的语境分析 ===\n")

    t0 = time.perf_counter()
                
    non_critical_chars = set()
    critical_records = []
    
    def find_critical(freq_list, source):
        critical = []
        idx = 0
        while idx < len(freq_list):
            char, freq = freq_list[idx]

            half_ratio = freq / target_char_count
            full_freq = total_counter[char]
            full_ratio = freq / full_freq if full_freq > 0 else 0

            if half_ratio > 0.5:
                critical.append({
                    'char': char,
                    'freq': freq,
                    'target_count': target_char_count,
                    'full_freq': full_freq,
                    'half_ratio': half_ratio,
                    'full_ratio': full_ratio,
                    'type': 'half_ratio',
                })
                idx += 1
            elif full_ratio > 0.8:
                critical.append({
                    'char': char,
                    'freq': freq,
                    'target_count': target_char_count,
                    'full_freq': full_freq,
                    'half_ratio': half_ratio,
                    'full_ratio': full_ratio,
                    'type': 'full_ratio',
                })
                idx += 1
            else:
                break
        return critical

    for target_char, target_char_count in top_chars:
        if print_analyze_chars_process:
            print(f"【字符：{target_char}】 出现总次数：{target_char_count}")
            
        matched_clauses = char_to_clauses.get(target_char, [])
        
        if print_analyze_chars_process:
            print(f"包含该字符的半句数量：{len(matched_clauses)}")

        if not matched_clauses:
            non_critical_chars.add(target_char)
            if print_analyze_chars_process:
                print(f"（无半句包含此字符，标记为非关键字符）\n")
            continue

        left_counter = Counter()
        right_counter = Counter()
        if print_analyze_chars_process:
            print("具体半句位置：")
        for i, clause in enumerate(matched_clauses, 1):
            pos_parts = []
            if clause.chapter_idx is not None:
                pos_parts.append(f"第{clause.chapter_idx}章")
            if clause.paragraph_idx is not None:
                pos_parts.append(f"第{clause.paragraph_idx}段")
            if clause.line_idx is not None:
                pos_parts.append(f"第{clause.line_idx}行")
            if clause.sentence_idx is not None:
                pos_parts.append(f"第{clause.sentence_idx}句")
            if clause.clause_idx is not None:
                pos_parts.append(f"第{clause.clause_idx}个半句")
            position = "、".join(pos_parts)
            if print_analyze_chars_process:
                print(f"  {i}. [{position}] {clause.text}")

            idx = clause.text.find(target_char)
            if idx == -1:
                continue

            # 只统计目标字符紧邻的单个字符
            # 检查左侧紧邻字符（idx - 1）
            if idx > 0:
                left_char = clause.text[idx - 1]
                if is_chinese_char(left_char) and left_char not in non_critical_chars:
                    left_counter[left_char] += 1

            # 检查右侧紧邻字符（idx + 1）
            if idx + 1 < len(clause.text):
                right_char = clause.text[idx + 1]
                if is_chinese_char(right_char) and right_char not in non_critical_chars:
                    right_counter[right_char] += 1
                    
        left_freq = left_counter.most_common()
        right_freq = right_counter.most_common()

        if print_analyze_chars_process:
            print(f"左部分字符频率列表（{len(left_freq)} 个唯一字符）:")
            print(left_freq[:max_freq_print])
            if len(left_freq) > max_freq_print:
                print(f"  （其余 {len(left_freq) - max_freq_print} 个未显示）")
            print(f"右部分字符频率列表（{len(right_freq)} 个唯一字符）:")
            print(right_freq[:max_freq_print])
            if len(right_freq) > max_freq_print:
                print(f"  （其余 {len(right_freq) - max_freq_print} 个未显示）")

        left_critical = find_critical(left_freq, 'left')
        right_critical = find_critical(right_freq, 'right')

        if not left_critical and not right_critical:
            non_critical_chars.add(target_char)
            if print_analyze_chars_process:
                print(f"左右部分均无关键字符，将 '{target_char}' 标记为非关键字符。（后续循环将忽略该字符）")
        else:
            if print_analyze_chars_process:
                print(f"左部分关键字符（判定条件：半句内占比 >0.5 或 该字符全文占比 >0.8）：")
                if left_critical:
                    for item in left_critical:
                        print(
                            f"  - '{item['char']}' (当前部分频率={item['freq']})："
                            f"半句内占比 = {item['freq']}/{item['target_count']} = {item['half_ratio']:.2f}，"
                            f"全文占比 = {item['freq']}/{item['full_freq']} = {item['full_ratio']:.2f} "
                            f"[判定依据：{item['type']}]"
                        )
                else:
                    print("  无")

                print(f"右部分关键字符：")
                if right_critical:
                    for item in right_critical:
                        print(
                            f"  - '{item['char']}' (当前部分频率={item['freq']})："
                            f"半句内占比 = {item['freq']}/{item['target_count']} = {item['half_ratio']:.2f}，"
                            f"全文占比 = {item['freq']}/{item['full_freq']} = {item['full_ratio']:.2f} "
                            f"[判定依据：{item['type']}]"
                        )
                else:
                    print("  无")

            for item in left_critical:
                critical_records.append((
                    target_char,
                    'left',
                    item['char'],
                    item['freq'],
                    item['target_count'],
                    item['full_freq'],
                    item['half_ratio'],
                    item['full_ratio'],
                    item['type']
                ))
            for item in right_critical:
                critical_records.append((
                    target_char,
                    'right',
                    item['char'],
                    item['freq'],
                    item['target_count'],
                    item['full_freq'],
                    item['half_ratio'],
                    item['full_ratio'],
                    item['type']
                ))
            
        if print_analyze_chars_process:
            print("\n" + "-" * 60 + "\n")

    if print_analyze_chars_process:
        print("=== 分析结果汇总 ===")
        print(f"非关键字符列表（左右均无关键字符的目标字符）：{sorted(non_critical_chars)}")
        print(f"关联字符记录（共 {len(critical_records)} 条）：")
    for rec in critical_records:
        target, source, char, freq, target_count, full_freq, half_ratio, full_ratio, ctype = rec
        type_desc = "半句内占比" if ctype == 'half_ratio' else "全文占比"
        if print_analyze_chars_process:
            print(
                f"  目标字符='{target}' 来源='{source}' 关联字符='{char}' "
                f"半句内占比={freq}/{target_count}={half_ratio:.2f} "
                f"全文占比={freq}/{full_freq}={full_ratio:.2f} "
                f"[判定依据：{type_desc}]"
            )
    
    t1 = time.perf_counter()
    print(f"\nanalyze_chars time: {t1 - t0:.6f}s\n")
    
    return critical_records, non_critical_chars


def extract_words_with_frequency(
    critical_records,
    all_clause_units,
    min_len=2,
    low_ls_ratio=0.4,
    high_ls_ratio=0.95,
):
    """
    从 critical_records 构建有向字符边，抽取实体词，并在 clause_texts 中统计词频。
    """

    clause_texts = [c.text for c in all_clause_units]
    
    # ---------- 1. Build directed edges ----------
    t0 = time.perf_counter()

    edges = set()
    for rec in critical_records:
        target, source, char = rec[0], rec[1], rec[2]
        if source == "right":
            u, v = target, char
        else:
            u, v = char, target
        edges.add((u, v))

    out_edges = defaultdict(list)
    for u, v in edges:
        out_edges[u].append(v)

    for u in list(out_edges):
        out_edges[u] = list(dict.fromkeys(out_edges[u]))

    print(
        f"extract/build edges time: {time.perf_counter() - t0:.6f}s | "
        f"edges={len(edges)} | nodes={len(out_edges)}"
    )

    # ---------- 2. Cached occurrence count ----------
    count_cache = {}

    def count_occ(word):
        c = count_cache.get(word)
        if c is None:
            c = sum(text.count(word) for text in clause_texts)
            count_cache[word] = c
        return c

    # ---------- 3. DFS candidate generation ----------
    max_paths = set()

    def evaluate_path(path):
        """
        Return True: stop extending this path.
        Return False: continue DFS.

        path length is always >= 2.
        """
        short_word = "".join(path[:-1])
        long_word = "".join(path)

        short_count = count_occ(short_word)
        long_count = count_occ(long_word)

        if short_count == 0:
            return True

        if short_count == 1:
            return False

        if len(short_word) >= min_len:
            ls_ratio = long_count / short_count

            if ls_ratio < low_ls_ratio:
                max_paths.add(short_word)
                return True

            if ls_ratio > high_ls_ratio:
                return False

            max_paths.add(short_word)
            return True

        return False

    def dfs(path):
        if evaluate_path(path):
            return

        last = path[-1]
        extensions = [
            nxt for nxt in out_edges.get(last, ())
            if nxt not in path
        ]

        if not extensions:
            word = "".join(path)
            if len(word) >= min_len and count_occ(word) > 0:
                max_paths.add(word)
            return

        for nxt in extensions:
            path.append(nxt)
            dfs(path)
            path.pop()

    for start, neighbours in out_edges.items():
        for nxt in neighbours:
            dfs([start, nxt])

    max_paths = {
        w for w in max_paths
        if len(w) >= min_len and count_occ(w) > 0
    }

    # ---------- 4. Greedy longest-match frequency counting ----------
    t0 = time.perf_counter()

    valid_words = set(max_paths)
    max_len = max((len(w) for w in valid_words), default=0)

    word_freq = Counter()

    for text in clause_texts:
        hits = Counter()
        i, n = 0, len(text)

        while i < n:
            matched = False
            for length in range(min(max_len, n - i), 0, -1):
                w = text[i:i + length]
                if w in valid_words:
                    hits[w] += 1
                    i += length
                    matched = True
                    break

            if not matched:
                i += 1

        word_freq.update(hits)

    print(
        f"count frequency time: {time.perf_counter() - t0:.6f}s | "
        f"words={len(max_paths)}"
    )

    return word_freq


def _apply_top_n(freq, top_n):
    """top_n 为 None 时原样返回；否则按频率取前 top_n 个。"""
    if top_n is None:
        return freq
    return Counter(dict(Counter(freq).most_common(top_n)))


def run_analysis(chapters, run_global, run_sum_local, top_n=None):
    """--analyze-all 与 --analyze-top-n 共用的分析流程。

    top_n is None  ->  --analyze-all 行为
    top_n is int   ->  --analyze-top-n 行为（按频率截取前 N 个实体）
    """
    all_clause_units = list(iter_units(chapters, 'clause'))

    if not all_clause_units:
        print("未找到任何半句。")
        return
    
    if run_sum_local:
        # ---------------------- Drink / Sum Local
        sum_local_word_freq = Counter()
        t1 = time.perf_counter()

        for chapter_idx, clauses_groupby_chap_iter in groupby(all_clause_units, key=lambda u: u.chapter_idx):
            print(f"\n\n文档标题:{chapters[chapter_idx - 1][0]}")
            print(f"文档长度:{len(chapters[chapter_idx - 1][1])}")
            
            clauses_groupby_chap = list(clauses_groupby_chap_iter)

            critical_records, non_critical_chars = analyze_chars(clauses_groupby_chap)
            word_freq = extract_words_with_frequency(critical_records, clauses_groupby_chap)
            word_freq = _apply_top_n(word_freq, top_n)
            print(f"local最终提取实体及其频率：{word_freq}")

            sum_local_word_freq.update(word_freq)

        sum_local_word_freq = _apply_top_n(sum_local_word_freq, top_n)

        print(f"sum local total time cost:{time.perf_counter() - t1:.6f}s")
        print(f"\n最终提取实体及其频率：{sum_local_word_freq}")
        
    if run_global:
        # ---------------------- Blink / Global
        t1 = time.perf_counter()

        critical_records, non_critical_chars = analyze_chars(all_clause_units)
        global_word_freq = extract_words_with_frequency(critical_records, all_clause_units)
        global_word_freq = _apply_top_n(global_word_freq, top_n)

        print(f"global total time cost:{time.perf_counter() - t1:.6f}s")
        print(f"最终提取实体及其频率：{global_word_freq}")


def main():
    args = sys.argv[1:]
    file_path = None
    unit = 'paragraph'
    analyze_top_n = False
    top_n = None
    analyze_all = False
    global_flag = False
    sum_local_flag = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--unit':
            if i + 1 < len(args):
                unit = args[i + 1]
                i += 2
            else:
                print("需要指定 --unit 的值，比如`--unit clause`")
                return
        elif arg == '--analyze-top-n':
            if i + 1 < len(args):
                try:
                    top_n = int(args[i + 1])
                    analyze_top_n = True
                    i += 2
                except ValueError:
                    print("--analyze-top-n 需要跟一个整数参数，比如`--analyze-top-n 20`")
                    return
            else:
                print("需要指定 --analyze-top-n 的值，比如`--analyze-top-n 20`")
                return
        elif arg == '--analyze-all':
            analyze_all = True
            i += 1
        elif arg == '--blink' or arg == '--global':
            global_flag = True
            i += 1
        elif arg == '--drink' or arg == '--sum-local':
            sum_local_flag = True
            i += 1
        elif arg.startswith('--'):
            print(f"未知参数: {arg}")
            return
        else:
            file_path = arg
            i += 1

    if analyze_top_n and analyze_all:
        print("错误：--analyze-top-n 和 --analyze-all 不能同时使用。")
        return

    if (global_flag or sum_local_flag) and not (analyze_top_n or analyze_all):
        print("错误：[--drink | --sum-local] / [--blink | --global] 只能与 --analyze-top-n 或 --analyze-all 一起使用。")
        return

    if global_flag or sum_local_flag:
        run_global = global_flag
        run_sum_local = sum_local_flag
    else:
        run_global = False
        run_sum_local = True

    if not file_path:
        print("错误：请提供txt文件路径。")
        print("用法: python script.py input.txt [--unit <unit>] [--analyze-top-n <n> | --analyze-all] [--drink | --sum-local] [--blink | --global] ")
        return

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
        return

    chapters = split_chapters(text)
    print(f"识别到 {len(chapters)} 章")

    if analyze_top_n or analyze_all:
        run_analysis(
            chapters,
            run_global=run_global,
            run_sum_local=run_sum_local,
            top_n=top_n if analyze_top_n else None,
        )
    else:
        print_stats(chapters, unit)


if __name__ == '__main__':
    main()
