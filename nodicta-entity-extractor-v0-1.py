import sys
import re
from collections import Counter
from collections import defaultdict
import time

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
    def __init__(self, text, chapter_idx=None, paragraph_idx=None, line_idx=None, sentence_idx=None, clause_idx=None):
        self.text = text
        self.chapter_idx = chapter_idx
        self.paragraph_idx = paragraph_idx
        self.line_idx = line_idx
        self.sentence_idx = sentence_idx
        self.clause_idx = clause_idx

        zh_chars = [ch for ch in text if is_chinese_char(ch)]
        self.total_chars = len(zh_chars)
        self.char_freq = Counter(zh_chars)
        self.char_freq_list = self.char_freq.most_common()
        self.unique_count = len(self.char_freq)


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
                            sentences = re.split(r'[。！？；!?;…...]', line)
                            sentences = [s.strip() for s in sentences if s.strip()]
                            for s_idx, sentence in enumerate(sentences, 1):
                                if unit == 'sentence':
                                    yield UnitInfo(sentence, chapter_idx=ch_idx, paragraph_idx=p_idx, line_idx=l_idx, sentence_idx=s_idx)
                                else:  # clause
                                    clauses = re.split(r'[，,；;：:、]', sentence)
                                    clauses = [c.strip() for c in clauses if c.strip()]
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
def analyze_chars(chapters, top_n=None, max_freq_print=20):
    """
    参数：
        top_n: 若指定，则只分析前 top_n 个最高频字符；若为 None，则分析所有出现次数 >1 的字符。
        max_freq_print: 打印左右频率列表时最多显示的条目数。

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
    
    all_clauses = list(iter_units(chapters, 'clause'))
    if not all_clauses:
        print("未找到任何半句。")
        return

    total_counter = Counter()
    for clause in all_clauses:
        total_counter.update(clause.char_freq)

    # 选择目标字符列表
    if top_n is not None:
        top_chars = [(char, count) for char, count in total_counter.most_common(top_n) if count > 1]
        print(f"=== 前 {top_n} 个最高频字符的语境分析 ===\n")
    else:
        top_chars = [(char, count) for char, count in total_counter.most_common() if count > 1]
        print("=== 出现过至少2次的字符语境分析 ===\n")

    t0 = time.perf_counter()
    
    non_critical_chars = set()
    critical_records = []

    for target_char, target_char_count in top_chars:
        print(f"【字符：{target_char}】 出现总次数：{target_char_count}")
        matched_clauses = [c for c in all_clauses if target_char in c.text]
        print(f"包含该字符的半句数量：{len(matched_clauses)}")

        if not matched_clauses:
            non_critical_chars.add(target_char)
            print(f"（无半句包含此字符，标记为非关键字符）\n")
            continue

        left_counter = Counter()
        right_counter = Counter()
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
            # 可取消下行注释以显示每个半句内容
            # print(f"  {i}. [{position}] {clause.text}")

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
                    
        left_freq = [(k, v) for k, v in left_counter.most_common() if v > 1]
        right_freq = [(k, v) for k, v in right_counter.most_common() if v > 1]

        print(f"左部分字符频率列表（{len(left_freq)} 个唯一字符）:")
        print(left_freq[:max_freq_print])
        if len(left_freq) > max_freq_print:
            print(f"  （其余 {len(left_freq) - max_freq_print} 个未显示）")
        print(f"右部分字符频率列表（{len(right_freq)} 个唯一字符）:")
        print(right_freq[:max_freq_print])
        if len(right_freq) > max_freq_print:
            print(f"  （其余 {len(right_freq) - max_freq_print} 个未显示）")

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

        left_critical = find_critical(left_freq, 'left')
        right_critical = find_critical(right_freq, 'right')

        if not left_critical and not right_critical:
            non_critical_chars.add(target_char)
            print(f"左右部分均无关键字符，将 '{target_char}' 标记为非关键字符。（后续循环将忽略该字符）")
        else:
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

        print("\n" + "-" * 60 + "\n")

    print("=== 分析结果汇总 ===")
    print(f"非关键字符列表（左右均无关键字符的目标字符）：{sorted(non_critical_chars)}")
    print(f"关联字符记录（共 {len(critical_records)} 条）：")
    for rec in critical_records:
        target, source, char, freq, target_count, full_freq, half_ratio, full_ratio, ctype = rec
        type_desc = "半句内占比" if ctype == 'half_ratio' else "全文占比"
        print(
            f"  目标字符='{target}' 来源='{source}' 关联字符='{char}' "
            f"半句内占比={freq}/{target_count}={half_ratio:.2f} "
            f"全文占比={freq}/{full_freq}={full_ratio:.2f} "
            f"[判定依据：{type_desc}]"
        )
    
    t1 = time.perf_counter()
    print(f"\nanalyze_chars time: {t1 - t0:.6f}s\n")
    
    return critical_records, non_critical_chars
    
    
def extract_words_with_frequency(critical_records, clause_texts):
    """
    基于字符关联和统计信息提取稳定词并统计频率。
    
    参数：
        critical_records: list of tuples，同前
        clause_texts: list of str，所有半句文本
    
    返回：
        dict, 词 -> 频率
    """

    # 1. 从 critical_records 提取有向边
    t0 = time.perf_counter()
    
    edges = set()
    for rec in critical_records:
        target, source, char = rec[0], rec[1], rec[2]
        if source == 'right':
            u, v = target, char
        else:
            u, v = char, target
        edges.add((u, v))
        
    t1 = time.perf_counter()
    print(f"extract edges time: {t1 - t0:.6f}s\n")
    print(f"edges:{edges}\nlength:{len(edges)}\n")
            
    # 2. 构建有向图（邻接表）
    t0 = time.perf_counter()
    
    out_edges = defaultdict(list)
    nodes = set()
    for u, v in edges:
        out_edges[u].append(v)
        nodes.add(u)
        nodes.add(v)
    
    t1 = time.perf_counter()
    print(f"build out_edges time: {t1 - t0:.6f}s\n")
    print(f"out_edges有向图:{out_edges}\nlength:{len(out_edges)}\n")

    # 3. 找出所有最大有向路径
    starts = list(out_edges.keys()) #开头字
    print(f"starts:{starts}\nlength:{len(starts)}\n")
        
    # DFS 提取最大路径
    not_entity = set()
    max_paths = set()
    
    def dfs(node, path, visited):
        if node in visited:
            return
        path.append(node)
        visited.add(node)
        
        if node not in out_edges or not out_edges[node]:
            if len(path) >= 2:
                if len(path) > 2:
                    tail_char = path[-2]
                    tail_char_followers = out_edges[tail_char]
                    if len(tail_char_followers) >= 2:
                        return
                    
                    short_word = ''.join(path[:-1])
                    long_word  = ''.join(path)
                    short_word_count = 0
                    long_word_count  = 0
                    if any(word in long_word[-2:] for word in not_entity):
                        for text in clause_texts:
                            short_word_count += text.count(short_word)
                        max_paths.add(short_word)
                        return
                    
                    for text in clause_texts:
                        short_word_count += text.count(short_word)
                        long_word_count  += text.count(long_word)

                    ls_ratio = long_word_count/short_word_count
                    if ls_ratio < 0.1:
                        if long_word_count > 0:
                            not_entity.add(long_word[-2:])
                        max_paths.add(short_word)
                        return
                    elif ls_ratio > 0.95:
                        max_paths.add(long_word)
                        return
                
                # Update and count word with char length < 2
                word = ''.join(path)
                if any(w == word for w in not_entity):
                    return
                else:
                    max_paths.add(word)
        else:
            for nxt in out_edges[node]:
                dfs(nxt, path[:], visited.copy())
    
    t0 = time.perf_counter()
    
    for start in starts:
        dfs(start, [], set())
        
    t1 = time.perf_counter()
    print(f"build max_paths time: {t1 - t0:.6f}s\n")
    print(f"not_entity:{not_entity}\n")
    
    # Remove not_entity words from max_paths
    max_paths -= not_entity
    
    def segment(text, dictionary):
        valid_words = {w for w, v in dictionary.items() if v > 0}
        if not valid_words:
            return text

        max_len = max(len(w) for w in valid_words)
        tokens = []
        i = 0
        n = len(text)

        while i < n:
            matched = False

            for length in range(min(max_len, n - i), 0, -1):
                word = text[i:i + length]
                if word in valid_words:
                    tokens.append(word)
                    i += length
                    matched = True
                    break

            if matched:
                continue

            start = i
            while i < n:
                match_at_i = False
                for length in range(min(max_len, n - i), 0, -1):
                    if text[i:i + length] in valid_words:
                        match_at_i = True
                        break
                if match_at_i:
                    break
                i += 1

            tokens.append(text[start:i])

        return '|'.join(tokens)
    
    # 4. 统计每个最大路径在原文本中的非重叠出现次数
    t0 = time.perf_counter()
    word_freq = Counter()
    final_substr_str_pairs = set()
    sorted_clause_texts = sorted(clause_texts, key=len)
    for text in sorted_clause_texts:
        tmp_substr_str_pairs = set()
        hits = {}
        for word in max_paths:
            c = text.count(word)
            if c > 0:
                hits[word] = c
        
        for a in hits:
            for b in hits:
                if a != b and a in b:
                    tmp_substr_str_pairs.add((a, b))
                    
        if tmp_substr_str_pairs:
            for substr, fullstr in tmp_substr_str_pairs:
                hits[substr] -= hits[fullstr]
                
        final_substr_str_pairs.update(tmp_substr_str_pairs)
        word_freq.update(hits)
        
    t1 = time.perf_counter()
    print(f"Count max_paths word frequency time: {t1 - t0:.6f}s\n")
    print(f"max_paths:{max_paths}\nlength:{len(max_paths)}\n")
    print(f"final_substr_str_pairs:{final_substr_str_pairs}\n")

    return word_freq


# ---------- 主流程 ----------
def main():
    args = sys.argv[1:]
    file_path = None
    unit = 'paragraph'
    analyze_top_n = False
    top_n = None
    analyze_all = False

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
        elif arg.startswith('--'):
            print(f"未知参数: {arg}")
            return
        else:
            file_path = arg
            i += 1

    if analyze_top_n and analyze_all:
        print("错误：--analyze-top-n 和 --analyze-all 不能同时使用。")
        return

    if not file_path:
        print("错误：请提供txt文件路径。")
        print("用法: python script.py input.txt [--unit <unit>] [--analyze-top-n <n> | --analyze-all]")
        return

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
        return

    chapters = split_chapters(text)
    print(f"识别到 {len(chapters)} 章")

    if analyze_top_n:
        critical_records, non_critical = analyze_chars(chapters, top_n=top_n)
        
        all_clauses = list(iter_units(chapters, 'clause'))
        clause_texts = [c.text for c in all_clauses]

        word_freq = extract_words_with_frequency(critical_records, clause_texts)
        print(f"最终提取实体及其频率：{word_freq}")
    elif analyze_all:
        critical_records, non_critical = analyze_chars(chapters, top_n=None)

        all_clauses = list(iter_units(chapters, 'clause'))
        clause_texts = [c.text for c in all_clauses]

        word_freq = extract_words_with_frequency(critical_records, clause_texts)
        print(f"最终提取实体及其频率：{word_freq}")
    else:
        print_stats(chapters, unit)
        
if __name__ == '__main__':
    main()
