from javsp.config import Cfg 
import logging

logger = logging.getLogger(__name__)

def prompt(message: str, what: str) -> str:
    if Cfg().other.interactive:
        return input(message)
    else:
        print(f"缺少{what}")
        import sys
        sys.exit(1)

def reviewMovieID(recognized: list, root):
    """
    手动核对扫描出的影片ID。
    如果是错误的ID，用户可以输入正确的ID或者输入's'跳过该影片。
    """
    from javsp.datatype import Movie
    import os
    
    if not Cfg().other.interactive:
        return

    print("\n" + "="*60)
    print("正在进入手动核对模式...")
    print("输入新的番号以更正，直接回车表示正确，输入 's' 跳过该影片")
    print("="*60 + "\n")

    for i, movie in enumerate(recognized):
        relpaths = [os.path.relpath(f, root) for f in movie.files]
        current_id = str(movie)
        
        msg = f"[{i+1}/{len(recognized)}] 识别结果: {current_id}\n    文件: {', '.join(relpaths)}\n    请输入新番号 (回车跳过修改): "
        user_input = input(msg).strip()
        
        if user_input.lower() == 's':
            logger.info(f"用户选择跳过影片: {current_id}")
            # 这里逻辑上需要能标记跳过，暂时仅记录
            continue
        elif user_input:
            new_movie = Movie(user_input)
            new_movie.files = movie.files
            recognized[i] = new_movie
            logger.info(f"已手动修正番号: {current_id} -> {user_input}")
    print("\n核对完成。\n")
