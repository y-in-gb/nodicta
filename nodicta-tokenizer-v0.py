import sys
import re
from collections import Counter

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
                            line = re.sub(r'["“”…...]', '', line)
                            sentences = re.split(r'[。！？；!?;]', line)
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

# ---------- 中文分词器 ----------
def tokenize_all_chars(chapters):
    # 1. 获取所有半句
    all_clauses = list(iter_units(chapters, 'clause'))
    if not all_clauses:
        print("未找到任何半句。")
        return

    # 2. 构建 char_lr_neighbor 字典
    char_lr_neighbor = {}
    
    # 3. 输出每个字符的左/右邻统计
    total_counter = Counter()
    for clause in all_clauses:
        total_counter.update(clause.char_freq)   # clause.char_freq 是基于 clause.text 的中文字符频率

    top_chars = total_counter.most_common()

    for target_char, target_char_count in top_chars:
        matched_clauses = [c for c in all_clauses if target_char in c.text]

        left_counter = Counter()
        right_counter = Counter()
       
        for clause in matched_clauses:
            idx = clause.text.find(target_char)
            left_char = clause.text[idx-1] if idx > 0 else ''
            right_char = clause.text[idx+1] if idx < len(clause.text)-1 else ''
            left_counter.update(left_char)
            right_counter.update(right_char)

        left_freq = left_counter.most_common()
        right_freq = right_counter.most_common()
        
        left_char_total = len(left_freq)
        right_char_total = len(right_freq)
        
        char_lr_neighbor[target_char] = {'target_total': target_char_count, 'left_total': left_char_total, 'right_total': right_char_total, 'left': {}, 'right': {}}
        char_lr_neighbor[target_char]['left'] = {char: count for char, count in left_freq}
        char_lr_neighbor[target_char]['right'] = {char: count for char, count in right_freq}

    # 4. 新增：利用 char_lr_neighbor 对每个半句进行切分（插入 '|'）
    print("\n--- 半句分割结果（加入 '|' 表示切分） ---")
    
    def segment_clause(clause_text):
        """根据 char_lr_neighbor 在 clause_text 中插入 '|'"""
        n = len(clause_text)
        if n <= 1:
            return [[0]]

        splits = set()  # 存储切分位置（在字符索引之后切分）
        
        char_to_total_list = []
        char_to_local_list = []
        

        for i in range(1, n):          # 只考虑有左右邻居的字符
            c = clause_text[i]
            l_c = clause_text[i - 1]
            
            has_r_c = False
            
            if i + 1 < n:
                r_c = clause_text[i + 1]
                has_r_c = True

            c_info = char_lr_neighbor.get(c)
            if not c_info:
                continue
            
            if i == 1:
                l_c_info = char_lr_neighbor.get(l_c)
                char_to_total_list.append((l_c,l_c_info['target_total']))
                
            char_to_total_list.append((c,c_info['target_total']))

            c_total_count = c_info['target_total']
            left_freq = c_info['left'].get(l_c, 0)
            if has_r_c:
                right_freq = c_info['right'].get(r_c, 0)
        
        char_total_digit = [len(str(v)) for k,v in char_to_total_list]

        def group_indices(arr, max_char_in_split=5):
            n = len(arr)

            result = []
            i = 0

            while i < n:
                # 1. Small valley: [x, x-1, x]
                if i + 2 < n and arr[i] == arr[i + 2] and arr[i] - 1 == arr[i + 1]:
                    result.append(list(range(i, i + 3)))
                    i += 3
                    continue

                # 2. Double twins: [x, x, x+1, x+1]
                if (i + 3 < n and
                    arr[i] == arr[i + 1] and
                    arr[i + 2] == arr[i + 3] and
                    arr[i + 2] == arr[i] + 1):
                    result.append(list(range(i, i + 4)))
                    i += 4
                    continue

                # 3. Non‑decreasing run (flat and/or climbing)
                end = i
                while end + 1 < n and arr[end] <= arr[end + 1]:
                    end += 1

                run_len = end - i + 1
                has_increase = arr[end] > arr[i]

                # If the run fits within the window and has at least one increase, take it whole
                if run_len <= max_char_in_split and has_increase:
                    # Check for a decrease after and a plateau at the end -> trim and create decreasing run
                    if (end + 1 < n and arr[end] > arr[end + 1] and run_len >= 2 and arr[end] == arr[end - 1]):
                        # Trim the last element
                        trimmed_end = end - 1
                        trimmed_len = trimmed_end - i + 1
                        if trimmed_len > 0:
                            result.append(list(range(i, trimmed_end + 1)))
                            i = trimmed_end + 1
                        # Now take the decreasing run of length 2
                        result.append(list(range(end, end + 2)))
                        i = end + 2
                        continue
                    else:
                        result.append(list(range(i, end + 1)))
                        i = end + 1
                        continue

                # Special handling for a long flat+climb (many equal elements then one increase)
                if run_len > max_char_in_split and has_increase:
                    # Check if it is exactly: flat part (all equal) then a single increase at the end
                    flat_len = 1
                    while i + flat_len < n and arr[i + flat_len] == arr[i]:
                        flat_len += 1

                    if flat_len == run_len - 1:   # flat then one increase
                        # Split the long flat+climb into smaller chunks
                        pos = i
                        remaining_flat = flat_len
                        # Take pairs of flats while more than 2 flats remain
                        while remaining_flat > 2:
                            result.append(list(range(pos, pos + 2)))
                            pos += 2
                            remaining_flat -= 2
                        # The last chunk contains the remaining flats and the increase
                        result.append(list(range(pos, end + 1)))
                        i = end + 1
                        continue
                    else:
                        # Fallback: take the first max_char_in_split elements
                        take = min(max_char_in_split, run_len)
                        result.append(list(range(i, i + take)))
                        i += take
                        continue

                # 4. Flat run without increase (all equal) – take as many equal as possible, split if needed
                if not has_increase and run_len >= 2:
                    pos = i
                    remaining = run_len
                    while remaining > 0:
                        take = min(max_char_in_split, remaining)
                        result.append(list(range(pos, pos + take)))
                        pos += take
                        remaining -= take
                    i = pos
                    continue

                # 5. Decreasing run (2‑char drop‑down or longer)
                end = i
                while end + 1 < n and arr[end] > arr[end + 1]:
                    end += 1
                if end > i:   # at least two elements decreasing
                    take = min(max_char_in_split, end - i + 1)
                    result.append(list(range(i, i + take)))
                    i += take
                    continue

                # 6. Fallback: single element
                result.append([i])
                i += 1

            return result
        
        splits = group_indices(char_total_digit)
        
        # 根据 splits 构建结果字符串
        return splits


    # 打印每个半句的切分结果
    for clause in all_clauses:
        text = clause.text

        # 获取当前半句的分组索引（需要 clause 对象提供 char_total_digit）
        splits = segment_clause(text)

        # 根据 splits 构建带 '|' 的字符串
        parts = []
        for idx_group in splits:
            # 每个 idx_group 是字符下标列表，取出对应字符并拼接
            part = ''.join(text[i] for i in idx_group)
            parts.append(part)
        segmented = '|'.join(parts)

        # （可选）组装位置信息
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

        # 打印最终结果（带位置信息，若不需要可只打印 segmented）
        print(f"[{position}] {segmented}")

    return


# ---------- 主流程 ----------
def main():
    # 检查命令行参数：必须提供一个txt文件路径
    if len(sys.argv) != 2:
        print("请提供一个txt文件作为命令行参数，例如: python script.py input.txt")
        return

    file_path = sys.argv[1]

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
        return

    chapters = split_chapters(text)
    print(f"识别到 {len(chapters)} 章")
    tokenize_all_chars(chapters)

if __name__ == '__main__':
    main()
