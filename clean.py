import re

def clean_requirements(input_file='requirements.txt', output_file='requirements_clean.txt'):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 要排除的模式
    exclude_patterns = [
        r'^anaconda-',      # 所有 anaconda- 开头的
        r'^conda==',        # conda 包
        r'^_?navigator',    # 导航器相关
        r'^bokeh==',        # 通常是 Anaconda 带的
        r'^botocore==',     # AWS SDK
        r'^bottleneck==',   # 性能优化
        r'^cloudpickle==',  # 序列化
        r'^dask==',         # 并行计算
        r'^datashape==',    # 数据形状
        r'^odo==',          # 数据迁移
        r'^partd==',        # 数据分区
        r'^pickleshare==',  # 数据共享
    ]
    
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # 检查是否匹配排除模式
        exclude = any(re.match(pattern, line, re.IGNORECASE) for pattern in exclude_patterns)
        
        if not exclude:
            cleaned_lines.append(line)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cleaned_lines))
    
    print(f"清理完成！原始 {len(lines)} 行，清理后 {len(cleaned_lines)} 行")
    print(f"已保存到: {output_file}")

if __name__ == '__main__':
    clean_requirements()