import xml.dom.minidom
import argparse
import os
import sys
from typing import Optional

class XMLFormatter:
    def __init__(self, indent_spaces: int = 2):
        """
        初始化XML格式化器
        
        Args:
            indent_spaces: 缩进空格数，默认为2
        """
        self.indent_spaces = indent_spaces
        
    def format_xml(self, xml_content: str) -> str:
        """
        格式化XML内容
        
        Args:
            xml_content: 原始XML字符串
            
        Returns:
            格式化后的XML字符串
        """
        try:
            # 解析XML
            dom = xml.dom.minidom.parseString(xml_content)
            
            # 获取格式化后的XML
            pretty_xml = dom.toprettyxml(indent=" " * self.indent_spaces)
            
            # 移除minidom添加的多余空行
            lines = []
            for line in pretty_xml.split('\n'):
                if line.strip():  # 跳过空行
                    lines.append(line)
            
            return '\n'.join(lines)
            
        except Exception as e:
            raise ValueError(f"XML解析错误: {str(e)}")
    
    def format_file(self, input_file: str, output_file: Optional[str] = None) -> None:
        """
        格式化XML文件
        
        Args:
            input_file: 输入XML文件路径
            output_file: 输出文件路径（如果为None，则打印到控制台）
        """
        # 检查文件是否存在
        if not os.path.exists(input_file):
            print(f"错误: 文件 '{input_file}' 不存在")
            sys.exit(1)
        
        # 读取文件
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(input_file, 'r', encoding='gbk') as f:
                xml_content = f.read()
        
        # 格式化XML
        try:
            formatted_xml = self.format_xml(xml_content)
            
            if output_file:
                # 写入输出文件
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(formatted_xml)
                print(f"XML已格式化并保存到: {output_file}")
            else:
                # 打印到控制台
                print("格式化后的XML:")
                print("-" * 50)
                print(formatted_xml)
                
        except ValueError as e:
            print(f"格式化失败: {e}")
            sys.exit(1)
    
    def format_string(self, xml_string: str) -> str:
        """
        格式化XML字符串
        
        Args:
            xml_string: 原始XML字符串
            
        Returns:
            格式化后的XML字符串
        """
        return self.format_xml(xml_string)


def main():
    """主函数：处理命令行参数"""
    parser = argparse.ArgumentParser(
        description='XML格式化工具 - 将XML文件整理格式并缩进输出',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s input.xml                    # 格式化并显示到控制台
  %(prog)s input.xml -o output.xml      # 格式化并保存到文件
  %(prog)s input.xml -i 4               # 使用4空格缩进
  %(prog)s input.xml --inplace          # 原地格式化（覆盖原文件）
        """
    )
    
    parser.add_argument('input', help='输入XML文件路径')
    parser.add_argument('-o', '--output', help='输出XML文件路径（可选）')
    parser.add_argument('-i', '--indent', type=int, default=2, 
                       help='缩进空格数（默认: 2）')
    parser.add_argument('--inplace', action='store_true',
                       help='原地格式化，覆盖输入文件')
    parser.add_argument('-v', '--version', action='version', 
                       version='XML格式化工具 v1.0')
    
    args = parser.parse_args()
    
    # 创建格式化器
    formatter = XMLFormatter(indent_spaces=args.indent)
    
    # 确定输出文件路径
    if args.inplace:
        output_file = args.input
    else:
        output_file = args.output
    
    # 执行格式化
    formatter.format_file(args.input, output_file)


if __name__ == "__main__":
    # 直接运行时的用法示例
    if len(sys.argv) > 1:
        main()
    else:
        print("XML格式化工具")
        print("=" * 50)
        
        # 交互式使用示例
        sample_xml = """<?xml version="1.0"?>
<root><person><name>张三</name><age>30</age><city>北京</city></person><person><name>李四</name><age>25</age><city>上海</city></person></root>"""
        
        print("示例1: 格式化字符串")
        formatter = XMLFormatter(indent_spaces=2)
        formatted = formatter.format_string(sample_xml)
        print("原始XML:")
        print(sample_xml)
        print("\n格式化后:")
        print(formatted)
        
        print("\n" + "=" * 50)
        print("使用方法:")
        print("1. 命令行: python xml_formatter.py input.xml [-o output.xml]")
        print("2. 作为模块导入:")
        print("   from xml_formatter import XMLFormatter")
        print("   formatter = XMLFormatter(indent_spaces=2)")
        print("   result = formatter.format_xml(xml_string)")