# 2026/01/16

FOR each step in prototype.steps:
    while step not completed:
        perceive screen
        ground step-required capabilities
        if executable:
            execute
            check step completion
        else:
            explore (bounded)
        if exploration exhausted:
            step failure


第一步：测试parse_current_screen
怎么实现？借助自动化框架？还是使用原生的ADB + uiautomator？

然而，后续还会涉及到对页面内某个元素的定位与操作（点击、输入、滑动、长按、返回等等），以上是否还支持？


完成了parse_current_screen

第二步：完成guided_exploration
难点：guided_exploration中的_map_capability_to_actions怎么实现？
我觉得必须重新思考一下


完成 _match_screen_to_target_tigs，需要测试一下？
完成 _select_capability_for_step，需要测试一下？
完成 _map_capability_to_actions，需要测试一下？