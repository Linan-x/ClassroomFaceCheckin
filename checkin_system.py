"""人脸识别会议签到系统 — 主入口

支持交互式菜单和命令行参数两种模式。

使用方式:
    交互模式:
        python checkin_system.py

    命令行模式:
        python checkin_system.py --create "会议名称" --desc "描述"
        python checkin_system.py --list
        python checkin_system.py --add-participant "会议名称" --name "张三" --photo photo.jpg
        python checkin_system.py --batch-add "会议名称" --src-dir src_path
        python checkin_system.py --build "会议名称"
        python checkin_system.py --checkin "会议名称"
        python checkin_system.py --report "会议名称"
        python checkin_system.py --export "会议名称" --format csv
"""

import argparse
import sys
from pathlib import Path

from config import get_config
from mtcnn import MTCNN
from Learner import face_learner

import course as meeting
import checkin
import report


def load_models(conf):
    """加载 MTCNN 和人脸识别模型（懒加载）"""
    print("正在加载 MTCNN...")
    mtcnn = MTCNN()
    print("MTCNN 加载完成")

    print("正在加载人脸识别模型...")
    learner = face_learner(conf, inference=True)
    learner.threshold = conf.threshold
    if conf.device.type == 'cpu':
        learner.load_state(conf, 'mobilefacenet.pth', True, True)
    else:
        learner.load_state(conf, 'mobilefacenet.pth', True, True)
    learner.model.eval()
    print("模型加载完成")
    return mtcnn, learner


def cmd_create(args):
    """创建新会议"""
    try:
        info = meeting.create_meeting(args.create, args.desc or "")
        print(f"会议 '{args.create}' 创建成功")
        return info
    except FileExistsError as e:
        print(f"错误: {e}")
        return None


def cmd_list(args):
    """列出所有会议"""
    meetings = meeting.list_meetings()
    if not meetings:
        print("暂无会议")
        return
    print(f"\n{'='*50}")
    print(f"  共 {len(meetings)} 个会议")
    print(f"{'='*50}")
    for m in meetings:
        name = m.get('name', '?')
        desc = m.get('description', '')
        pcount = m.get('participant_count', 0)
        ccount = m.get('checked_in', 0)
        desc_str = f" - {desc}" if desc else ""
        print(f"  [{name}]{desc_str}")
        print(f"    参与者: {pcount} 人 | 已签到: {ccount} 人")
    print()


def cmd_add_participant(args):
    """添加参与者"""
    try:
        path = meeting.add_participant(args.add_participant, args.name, args.photo)
        print(f"参与者 '{args.name}' 添加成功: {path}")
        print("提示: 添加参与者后需要执行 --build 重建特征库")
    except (FileNotFoundError, FileExistsError) as e:
        print(f"错误: {e}")


def cmd_batch_add(args):
    """批量添加参与者"""
    try:
        added = meeting.add_participants_from_dir(args.batch_add, args.src_dir)
        print(f"批量添加完成，共添加 {len(added)} 人: {', '.join(added)}")
        print("提示: 添加参与者后需要执行 --build 重建特征库")
    except FileNotFoundError as e:
        print(f"错误: {e}")


def cmd_build(args):
    """重建特征库"""
    conf = get_config(False)
    mtcnn, learner = load_models(conf)
    try:
        embs, names = meeting.build_facebank(
            args.build, learner.model, mtcnn, conf, tta=True
        )
    except FileNotFoundError as e:
        print(f"错误: {e}")


def cmd_checkin(args):
    """启动签到"""
    conf = get_config(False)
    mtcnn, learner = load_models(conf)
    conf.face_limit = 10
    conf.min_face_size = 30
    checkin.start_checkin(
        args.checkin, learner, mtcnn, conf,
        threshold=args.threshold, tta=not args.no_tta
    )


def cmd_report(args):
    """查看签到报告"""
    try:
        report.show_report(args.report)
    except Exception as e:
        print(f"错误: {e}")


def cmd_export(args):
    """导出签到结果"""
    try:
        if args.format == 'csv':
            report.export_csv(args.export)
        elif args.format == 'html':
            report.export_html(args.export)
        else:
            print(f"不支持的格式: {args.format}，可选: csv, html")
    except Exception as e:
        print(f"错误: {e}")


def cmd_take_photo(args):
    """拍照注册参与者"""
    conf = get_config(False)
    mtcnn, _ = load_models(conf)
    try:
        meeting.take_participant_photo(args.take_photo, args.name, mtcnn)
        print("提示: 拍照后需要执行 --build 重建特征库")
    except Exception as e:
        print(f"错误: {e}")


def interactive_menu():
    """交互式菜单"""
    conf = get_config(False)
    mtcnn, learner = None, None  # 懒加载
    current_meeting = None

    def ensure_models():
        nonlocal mtcnn, learner
        if mtcnn is None or learner is None:
            mtcnn, learner = load_models(conf)
        return mtcnn, learner

    def select_meeting():
        nonlocal current_meeting
        meetings = meeting.list_meetings()
        if not meetings:
            print("暂无会议，请先创建")
            return None
        print("\n选择会议:")
        for i, m in enumerate(meetings, 1):
            name = m.get('name', '?')
            desc = m.get('description', '')
            desc_str = f" - {desc}" if desc else ""
            print(f"  {i}. {name}{desc_str}")
        print("  0. 返回")
        try:
            choice = int(input("请输入编号: "))
            if choice == 0:
                return current_meeting
            if 1 <= choice <= len(meetings):
                current_meeting = meetings[choice - 1]['name']
                print(f"已选择会议: {current_meeting}")
                return current_meeting
        except (ValueError, IndexError):
            pass
        print("无效选择")
        return current_meeting

    while True:
        print(f"\n{'='*45}")
        print(f"  人脸识别会议签到系统")
        print(f"{'='*45}")
        if current_meeting:
            # 获取当前会议统计
            try:
                stats = report.get_statistics(current_meeting)
                print(f"  当前会议: {current_meeting}")
                print(f"  参与者: {stats['total_participants']}人 | 已签到: {stats['checked_in']}人")
            except Exception:
                print(f"  当前会议: {current_meeting}")
        else:
            print(f"  当前会议: (未选择)")
        print(f"{'='*45}")
        print(f"  1. 创建新会议")
        print(f"  2. 选择/查看会议列表")
        print(f"  3. 添加参与者")
        print(f"  4. 拍照注册参与者")
        print(f"  5. 批量添加参与者")
        print(f"  6. 构建特征库 (Facebank)")
        print(f"  7. 开始签到")
        print(f"  8. 查看签到报告")
        print(f"  9. 导出签到结果")
        print(f"  0. 退出")
        print(f"{'='*45}")

        choice = input("请选择操作: ").strip()

        if choice == '1':
            name = input("会议名称: ").strip()
            if not name:
                print("会议名称不能为空")
                continue
            desc = input("会议描述 (可选): ").strip()
            try:
                meeting.create_meeting(name, desc)
                print(f"会议 '{name}' 创建成功")
                current_meeting = name
            except FileExistsError as e:
                print(f"错误: {e}")

        elif choice == '2':
            current_meeting = select_meeting()

        elif choice == '3':
            if not current_meeting:
                print("请先选择会议")
                continue
            name = input("参与者姓名: ").strip()
            if not name:
                print("姓名不能为空")
                continue
            photo = input("照片路径: ").strip()
            if not photo:
                print("照片路径不能为空")
                continue
            try:
                meeting.add_participant(current_meeting, name, photo)
                print(f"参与者 '{name}' 添加成功")
                print("提示: 请选择 6 构建特征库")
            except Exception as e:
                print(f"错误: {e}")

        elif choice == '4':
            if not current_meeting:
                print("请先选择会议")
                continue
            name = input("参与者姓名: ").strip()
            if not name:
                print("姓名不能为空")
                continue
            ensure_models()
            try:
                meeting.take_participant_photo(current_meeting, name, mtcnn)
                print("提示: 请选择 6 构建特征库")
            except Exception as e:
                print(f"错误: {e}")

        elif choice == '5':
            if not current_meeting:
                print("请先选择会议")
                continue
            src = input("源目录路径 (目录结构: src/<姓名>/<照片>): ").strip()
            if not src:
                print("路径不能为空")
                continue
            try:
                added = meeting.add_participants_from_dir(current_meeting, src)
                print(f"批量添加完成，共 {len(added)} 人: {', '.join(added)}")
                print("提示: 请选择 6 构建特征库")
            except Exception as e:
                print(f"错误: {e}")

        elif choice == '6':
            if not current_meeting:
                print("请先选择会议")
                continue
            ensure_models()
            try:
                meeting.build_facebank(current_meeting, learner.model, mtcnn, conf, tta=True)
            except Exception as e:
                print(f"错误: {e}")

        elif choice == '7':
            if not current_meeting:
                print("请先选择会议")
                continue
            ensure_models()
            # 检查 facebank 是否存在
            fb_path = Path(f'data/meetings/{current_meeting}/facebank.pth')
            if not fb_path.exists():
                print(f"特征库不存在，请先选择 6 构建特征库")
                yn = input("现在构建? (y/n): ").strip().lower()
                if yn == 'y':
                    try:
                        meeting.build_facebank(current_meeting, learner.model, mtcnn, conf, tta=True)
                    except Exception as e:
                        print(f"构建失败: {e}")
                        continue
                else:
                    continue
            conf.face_limit = 10
            conf.min_face_size = 30
            checkin.start_checkin(current_meeting, learner, mtcnn, conf)

        elif choice == '8':
            if not current_meeting:
                print("请先选择会议")
                continue
            try:
                report.show_report(current_meeting)
            except Exception as e:
                print(f"错误: {e}")

        elif choice == '9':
            if not current_meeting:
                print("请先选择会议")
                continue
            print("导出格式: 1. CSV  2. HTML")
            fmt_choice = input("请选择: ").strip()
            try:
                if fmt_choice == '1':
                    report.export_csv(current_meeting)
                elif fmt_choice == '2':
                    report.export_html(current_meeting)
                else:
                    print("无效选择")
            except Exception as e:
                print(f"错误: {e}")

        elif choice == '0':
            print("感谢使用，再见！")
            break

        else:
            print("无效选择，请重新输入")


def main():
    parser = argparse.ArgumentParser(description='人脸识别会议签到系统')
    # 会议管理
    parser.add_argument('--create', type=str, help='创建新会议')
    parser.add_argument('--desc', type=str, default='', help='会议描述')
    parser.add_argument('--list', action='store_true', help='列出所有会议')
    # 参与者管理
    parser.add_argument('--add-participant', type=str, help='添加参与者到指定会议（需配合 --name --photo）')
    parser.add_argument('--name', type=str, help='参与者姓名')
    parser.add_argument('--photo', type=str, help='照片路径')
    parser.add_argument('--batch-add', type=str, help='批量添加参与者（需配合 --src-dir）')
    parser.add_argument('--src-dir', type=str, help='源目录路径')
    parser.add_argument('--take-photo', type=str, help='拍照注册参与者到指定会议（需配合 --name）')
    # Facebank
    parser.add_argument('--build', type=str, help='构建/更新特征库')
    # 签到
    parser.add_argument('--checkin', type=str, help='启动签到')
    parser.add_argument('--threshold', type=float, default=1.54, help='识别阈值')
    parser.add_argument('--no-tta', action='store_true', help='禁用测试时增强')
    # 报告
    parser.add_argument('--report', type=str, help='查看签到报告')
    parser.add_argument('--export', type=str, help='导出签到结果（需配合 --format）')
    parser.add_argument('--format', type=str, default='csv', choices=['csv', 'html'], help='导出格式')

    args = parser.parse_args()

    # 如果没有参数，进入交互模式
    has_args = any(v is not None and v is not False for k, v in vars(args).items()
                   if k not in ('threshold', 'format', 'desc', 'name', 'photo', 'src_dir', 'no_tta'))
    if not has_args:
        interactive_menu()
        return

    # 命令行模式
    if args.list:
        cmd_list(args)
    elif args.create:
        cmd_create(args)
    elif args.add_participant:
        cmd_add_participant(args)
    elif args.batch_add:
        cmd_batch_add(args)
    elif args.take_photo:
        cmd_take_photo(args)
    elif args.build:
        cmd_build(args)
    elif args.checkin:
        cmd_checkin(args)
    elif args.report:
        cmd_report(args)
    elif args.export:
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
