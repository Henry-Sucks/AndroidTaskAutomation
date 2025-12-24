# 2025/12/22

目前我生成了如下的流程：

自然语言任务 -》 GlobalPlanner根据global_index拆解成簇内的subtask -》 LocalPlanner根据subtask，在簇内找到对应的intent和页面上的动作（edge）

问题1：没有给出当前页面的信息
问题2：给出了这些subtask，我们假定是可以实现相应功能的，然后如何将其连接起来？


可以看到，子任务划分是对的，但这用到了global_index的支持吗？
cluster的summary令人不满意，如何解决？
```
Original task: 搜索“周杰伦”的歌曲并播放，然后添加到我的收藏夹。
[1] cluster_id=30 | sub_task=Search for songs by '周杰伦' within the app.
    actions: <empty>
    summary: This cluster enables users to explore, navigate, and interact with a comprehensive music and audio streaming app, including browsing playlists, switching between music genres and content types (like podcasts and audiobooks), managing playback, and discovering new content through recommendations and charts.
    supported_intents: Browse and explore music playlists and curated collections; Navigate between different music genres, categories, and app sections (Music, Podcasts, Audiobooks); Control music playback and manage the current playlist or queue; Discover new music through recommendations, rankings, and trending charts; Access exclusive or premium content (e.g., VIP sections, original music); View detailed information about songs, artists, and playlists
[2] cluster_id=26 | sub_task=Select and initiate playback of a specific song from the search results.
    actions: <empty>
    summary: Users interact with playlist and song list views to browse, play, and manage music tracks, with particular focus on exploring popular charts, accessing VIP/paid content details, and performing playlist management actions.
    supported_intents: Browse and explore songs within a playlist or chart (e.g., Hot Songs Chart); Play specific songs or manage playback from a list; View detailed information about songs, including VIP/paid content restrictions and pricing; Manage playlist contents (e.g., search, sort, select songs for download/deletion); Access playlist statistics and user engagement features (e.g., comments, shares, play counts); Navigate within the playlist interface and access contextual song options
[3] cluster_id=75 | sub_task=Add the currently playing song to your favorites or collection.
    actions: <empty>
    summary: This cluster enables users to engage deeply with the music they are playing, allowing them to explore song details, interact with artists, and share music socially. It focuses on moving between the player, song/artist information, and sharing features to enhance the listening experience.        
    supported_intents: Explore detailed information about the currently playing song and its artist; Save or favorite songs and artists for later access; Share the currently playing song with friends or on social platforms; Navigate between the music player, playlists, and artist profiles; Initiate a shared listening session with others; View and interact with song comments and community features
Original task: 搜索“周杰伦”的歌曲并播放，然后添加到我的收藏夹。
[1] cluster_id=30
    sub_task: Search for songs by '周杰伦' within the app.
    matched_intent: The user is searching for music, artists, or songs within the app by interacting with the search bar.
    actions: 1 steps
      (1) CLICK @ C358B79A721B9728C928058B95FA360C
           xpath: /android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/androidx.drawerlayout.widget.DrawerLayout/android.widget.FrameLayout/android.widget.RelativeLayout/android.view.ViewGroup/androidx.viewpager.widget.ViewPager/androidx.recyclerview.widget.RecyclerView/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout[0]/android.widget.LinearLayout/android.widget.LinearLayout/android.widget.ImageView
[2] cluster_id=26
    sub_task: Select and initiate playback of a specific song from the search results.
    matched_intent: The user is navigating through a playlist to select or view details of a specific song.
    actions: 1 steps
      (1) CLICK @ 93274F508507AB30DD95CF4AD31AF119
           xpath: /android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout[3]/android.widget.FrameLayout/android.view.ViewGroup[0]/androidx.recyclerview.widget.RecyclerView/android.widget.LinearLayout[1]
[3] cluster_id=75
    sub_task: Add the currently playing song to your favorites or collection.
    matched_intent: The user wants to share the currently playing song with friends or other apps.     
    actions: 1 steps
      (1) CLICK @ 4CAB0F98A55165DD34B1F8E776E964B3
           xpath: /android.widget.FrameLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.RelativeLayout/android.view.ViewGroup/androidx.appcompat.widget.LinearLayoutCompat/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.RelativeLayout
```

# 2025/12/24

现在的问题：
1. 喂给大模型的模式：

簇的summary；
簇中的能完成的子功能；

这样做和KG-RAG有什么区别？
似乎可以把这个问题放放；

2. 现在的效果极差：
有两个改进的方向：
- 最根本的是：修改分簇的算法，得到更精准的算法；
- 修改总结簇的summary和子任务的prompt，让intent和簇之间的差异更加显著；


注意到了：由于先前Node状态的合并，导致许多应该出现新内容的操作最后被判断没有出现新的内容（比如说SWIPE）。需要解决？


先给定一个ground_truth吧：

打开弹出搜索框：
cluster_35_intent_213_The_user_wants_to_search_for_music_or_explore_tren
cluster_35_intent_66_The_user_wants_to_search_for_music__videos__podcas
The user is searching for music, artists, or songs within the app by interacting with the search bar.

搜索框到单曲主页
cluster_35_intent_160_The_user_wants_to_search_for_content_related_to__郑

单曲主页到歌曲页面

歌曲页面到收藏




