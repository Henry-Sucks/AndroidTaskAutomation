var nodes = [
  {
    id: "ffe1f73322a3",
    step: 1,
    activity: "net.gsantner.markor.activity.IntroActivity",
    image: "s0001.png",
    xml: "s0001.xml"
  },
  {
    id: "2b4bebd52c4e",
    step: 3,
    activity: "net.gsantner.markor.activity.IntroActivity",
    image: "s0003.png",
    xml: "s0003.xml"
  },
  {
    id: "f447b02ec6c7",
    step: 9,
    activity: "net.gsantner.markor.activity.IntroActivity",
    image: "s0009.png",
    xml: "s0009.xml"
  },
  {
    id: "ee8dc65b7068",
    step: 19,
    activity: "net.gsantner.markor.activity.IntroActivity",
    image: "s0019.png",
    xml: "s0019.xml"
  },
  {
    id: "cdecd7e5e19c",
    step: 39,
    activity: "net.gsantner.markor.activity.IntroActivity",
    image: "s0039.png",
    xml: "s0039.xml"
  },
  {
    id: "aa9d4c0cb76f",
    step: 45,
    activity: "net.gsantner.markor.activity.IntroActivity",
    image: "s0045.png",
    xml: "s0045.xml"
  },
  {
    id: "f441effa616e",
    step: 110,
    activity: "net.gsantner.markor.activity.IntroActivity",
    image: "s0110.png",
    xml: "s0110.xml"
  }
];

var edges = [
  {
    id: "ffe1f73322a3-->ffe1f73322a3",
    tag: "e0002",
    step: 2,
    from: "ffe1f73322a3",
    to: "ffe1f73322a3",
    raw_action: "g0a8[1,1][1]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=36][T=0][][S=1.000000][RN=1][0,1350,1080,1900][Notebook]"
  },
  {
    id: "ffe1f73322a3-->2b4bebd52c4e",
    tag: "e0003",
    step: 3,
    from: "ffe1f73322a3",
    to: "2b4bebd52c4e",
    raw_action: "g0a4[2,2][1]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=52][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#49d97430]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0004",
    step: 4,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a1[3,3][1]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=36][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0005",
    step: 5,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a0[4,4][1]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=44][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0006",
    step: 6,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a7[5,5][1]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=52][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0007",
    step: 7,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a6[6,6][1]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=36][T=0][][S=1.000000][RN=1][0,66,1080,433][View]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0008",
    step: 8,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a5[7,7][1]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=52][T=0][][S=1.000000][RN=1][0,66,1080,433][View]"
  },
  {
    id: "2b4bebd52c4e-->f447b02ec6c7",
    tag: "e0009",
    step: 9,
    from: "2b4bebd52c4e",
    to: "f447b02ec6c7",
    raw_action: "g0a2[8,8][1]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=44][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->ffe1f73322a3",
    tag: "e0010",
    step: 10,
    from: "f447b02ec6c7",
    to: "ffe1f73322a3",
    raw_action: "g0a5[7,9][2]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=50][T=0][][S=1.000000][RN=1][0,66,1080,433][Main Vie]"
  },
  {
    id: "ffe1f73322a3-->f447b02ec6c7",
    tag: "e0011",
    step: 11,
    from: "ffe1f73322a3",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,10][1]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=36][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->2b4bebd52c4e",
    tag: "e0012",
    step: 12,
    from: "f447b02ec6c7",
    to: "2b4bebd52c4e",
    raw_action: "g0a7[5,11][2]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=50][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "2b4bebd52c4e-->ffe1f73322a3",
    tag: "e0013",
    step: 13,
    from: "2b4bebd52c4e",
    to: "ffe1f73322a3",
    raw_action: "g0a9[12,12][1]@MODEL_BACKg0s0[1,13][13]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=13][T=0][]"
  },
  {
    id: "ffe1f73322a3-->ffe1f73322a3",
    tag: "e0014",
    step: 14,
    from: "ffe1f73322a3",
    to: "ffe1f73322a3",
    raw_action: "g0a0[4,13][2]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ffe1f73322a3-->ffe1f73322a3",
    tag: "e0015",
    step: 15,
    from: "ffe1f73322a3",
    to: "ffe1f73322a3",
    raw_action: "g0a1[3,14][2]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ffe1f73322a3-->ffe1f73322a3",
    tag: "e0016",
    step: 16,
    from: "ffe1f73322a3",
    to: "ffe1f73322a3",
    raw_action: "g0a2[8,15][2]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ffe1f73322a3-->f447b02ec6c7",
    tag: "e0017",
    step: 17,
    from: "ffe1f73322a3",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,16][2]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->2b4bebd52c4e",
    tag: "e0018",
    step: 18,
    from: "f447b02ec6c7",
    to: "2b4bebd52c4e",
    raw_action: "g0a6[6,17][2]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=30][T=0][][S=1.000000][RN=1][0,66,1080,433][View]"
  },
  {
    id: "2b4bebd52c4e-->ee8dc65b7068",
    tag: "e0019",
    step: 19,
    from: "2b4bebd52c4e",
    to: "ee8dc65b7068",
    raw_action: "g0a4[2,18][2]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#3d87c8a7]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0020",
    step: 20,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a8[1,19][2]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->2b4bebd52c4e",
    tag: "e0021",
    step: 21,
    from: "ee8dc65b7068",
    to: "2b4bebd52c4e",
    raw_action: "g0a9[12,20][2]@MODEL_BACKg0s0[1,21][21]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0022",
    step: 22,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a0[4,21][3]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0023",
    step: 23,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a1[3,22][3]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->f447b02ec6c7",
    tag: "e0024",
    step: 24,
    from: "2b4bebd52c4e",
    to: "f447b02ec6c7",
    raw_action: "g0a2[8,23][3]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->f447b02ec6c7",
    tag: "e0025",
    step: 25,
    from: "f447b02ec6c7",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,24][3]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->ee8dc65b7068",
    tag: "e0026",
    step: 26,
    from: "f447b02ec6c7",
    to: "ee8dc65b7068",
    raw_action: "g0a4[2,25][3]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#53d644a7]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0027",
    step: 27,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,26][3]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0028",
    step: 28,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,27][3]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0029",
    step: 29,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a7[5,28][3]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0030",
    step: 30,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a8[1,29][3]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->2b4bebd52c4e",
    tag: "e0031",
    step: 31,
    from: "ee8dc65b7068",
    to: "2b4bebd52c4e",
    raw_action: "g0a9[12,30][3]@MODEL_BACKg0s0[1,31][31]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0032",
    step: 32,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a0[4,31][4]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0033",
    step: 33,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a1[3,32][4]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->f447b02ec6c7",
    tag: "e0034",
    step: 34,
    from: "2b4bebd52c4e",
    to: "f447b02ec6c7",
    raw_action: "g0a2[8,33][4]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->f447b02ec6c7",
    tag: "e0035",
    step: 35,
    from: "f447b02ec6c7",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,34][4]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->ee8dc65b7068",
    tag: "e0036",
    step: 36,
    from: "f447b02ec6c7",
    to: "ee8dc65b7068",
    raw_action: "g0a4[2,35][4]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#53d644a7]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0037",
    step: 37,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,36][4]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0038",
    step: 38,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,37][4]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->cdecd7e5e19c",
    tag: "e0039",
    step: 39,
    from: "ee8dc65b7068",
    to: "cdecd7e5e19c",
    raw_action: "g0a4[2,38][5]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#c0c234a7]"
  },
  {
    id: "cdecd7e5e19c-->cdecd7e5e19c",
    tag: "e0040",
    step: 40,
    from: "cdecd7e5e19c",
    to: "cdecd7e5e19c",
    raw_action: "g0a7[5,39][4]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][Manage y]"
  },
  {
    id: "cdecd7e5e19c-->cdecd7e5e19c",
    tag: "e0041",
    step: 41,
    from: "cdecd7e5e19c",
    to: "cdecd7e5e19c",
    raw_action: "g0a8[1,40][4]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][Manage y]"
  },
  {
    id: "cdecd7e5e19c-->ee8dc65b7068",
    tag: "e0042",
    step: 42,
    from: "cdecd7e5e19c",
    to: "ee8dc65b7068",
    raw_action: "g0a9[12,41][4]@MODEL_BACKg0s0[1,42][42]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0043",
    step: 43,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a0[4,42][5]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0044",
    step: 44,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a1[3,43][5]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ee8dc65b7068-->aa9d4c0cb76f",
    tag: "e0045",
    step: 45,
    from: "ee8dc65b7068",
    to: "aa9d4c0cb76f",
    raw_action: "g0a2[8,44][5]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "aa9d4c0cb76f-->aa9d4c0cb76f",
    tag: "e0046",
    step: 46,
    from: "aa9d4c0cb76f",
    to: "aa9d4c0cb76f",
    raw_action: "g0a3[10,45][5]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "aa9d4c0cb76f-->ee8dc65b7068",
    tag: "e0047",
    step: 47,
    from: "aa9d4c0cb76f",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,46][5]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->cdecd7e5e19c",
    tag: "e0048",
    step: 48,
    from: "ee8dc65b7068",
    to: "cdecd7e5e19c",
    raw_action: "g0a4[2,47][6]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#53d644a7]"
  },
  {
    id: "cdecd7e5e19c-->cdecd7e5e19c",
    tag: "e0049",
    step: 49,
    from: "cdecd7e5e19c",
    to: "cdecd7e5e19c",
    raw_action: "g0a6[6,48][5]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][To-Do]"
  },
  {
    id: "cdecd7e5e19c-->cdecd7e5e19c",
    tag: "e0050",
    step: 50,
    from: "cdecd7e5e19c",
    to: "cdecd7e5e19c",
    raw_action: "g0a7[5,49][5]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][Manage y]"
  },
  {
    id: "cdecd7e5e19c-->cdecd7e5e19c",
    tag: "e0051",
    step: 51,
    from: "cdecd7e5e19c",
    to: "cdecd7e5e19c",
    raw_action: "g0a8[1,50][5]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][Manage y]"
  },
  {
    id: "cdecd7e5e19c-->ee8dc65b7068",
    tag: "e0052",
    step: 52,
    from: "cdecd7e5e19c",
    to: "ee8dc65b7068",
    raw_action: "g0a9[12,51][5]@MODEL_BACKg0s0[1,52][52]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0053",
    step: 53,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a0[4,52][6]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0054",
    step: 54,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a1[3,53][6]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0055",
    step: 55,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a1[3,54][7]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ee8dc65b7068-->aa9d4c0cb76f",
    tag: "e0056",
    step: 56,
    from: "ee8dc65b7068",
    to: "aa9d4c0cb76f",
    raw_action: "g0a2[8,55][6]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "aa9d4c0cb76f-->aa9d4c0cb76f",
    tag: "e0057",
    step: 57,
    from: "aa9d4c0cb76f",
    to: "aa9d4c0cb76f",
    raw_action: "g0a3[10,56][6]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "aa9d4c0cb76f-->ee8dc65b7068",
    tag: "e0058",
    step: 58,
    from: "aa9d4c0cb76f",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,57][6]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0059",
    step: 59,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,58][6]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0060",
    step: 60,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a7[5,59][6]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0061",
    step: 61,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a8[1,60][6]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->2b4bebd52c4e",
    tag: "e0062",
    step: 62,
    from: "ee8dc65b7068",
    to: "2b4bebd52c4e",
    raw_action: "g0a9[12,61][6]@MODEL_BACKg0s0[1,62][62]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0063",
    step: 63,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a0[4,62][7]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->f447b02ec6c7",
    tag: "e0064",
    step: 64,
    from: "2b4bebd52c4e",
    to: "f447b02ec6c7",
    raw_action: "g0a2[8,63][7]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->f447b02ec6c7",
    tag: "e0065",
    step: 65,
    from: "f447b02ec6c7",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,64][7]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->aa9d4c0cb76f",
    tag: "e0066",
    step: 66,
    from: "f447b02ec6c7",
    to: "aa9d4c0cb76f",
    raw_action: "g0a4[2,65][7]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#d0d49ca7]"
  },
  {
    id: "aa9d4c0cb76f-->ee8dc65b7068",
    tag: "e0067",
    step: 67,
    from: "aa9d4c0cb76f",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,66][7]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0068",
    step: 68,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,67][7]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0069",
    step: 69,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a7[5,68][7]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0070",
    step: 70,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a8[1,69][7]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->cdecd7e5e19c",
    tag: "e0071",
    step: 71,
    from: "ee8dc65b7068",
    to: "cdecd7e5e19c",
    raw_action: "g0a4[2,70][8]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#53d644a7]"
  },
  {
    id: "cdecd7e5e19c-->ee8dc65b7068",
    tag: "e0072",
    step: 72,
    from: "cdecd7e5e19c",
    to: "ee8dc65b7068",
    raw_action: "g0a9[12,71][7]@MODEL_BACKg0s0[1,72][72]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0073",
    step: 73,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a0[4,72][8]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0074",
    step: 74,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a1[3,73][8]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "ee8dc65b7068-->aa9d4c0cb76f",
    tag: "e0075",
    step: 75,
    from: "ee8dc65b7068",
    to: "aa9d4c0cb76f",
    raw_action: "g0a2[8,74][8]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "aa9d4c0cb76f-->aa9d4c0cb76f",
    tag: "e0076",
    step: 76,
    from: "aa9d4c0cb76f",
    to: "aa9d4c0cb76f",
    raw_action: "g0a3[10,75][8]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "aa9d4c0cb76f-->ee8dc65b7068",
    tag: "e0077",
    step: 77,
    from: "aa9d4c0cb76f",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,76][8]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0078",
    step: 78,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,77][8]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0079",
    step: 79,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a7[5,78][8]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0080",
    step: 80,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a8[1,79][8]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->2b4bebd52c4e",
    tag: "e0081",
    step: 81,
    from: "ee8dc65b7068",
    to: "2b4bebd52c4e",
    raw_action: "g0a9[12,80][8]@MODEL_BACKg0s0[1,81][81]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0082",
    step: 82,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a0[4,81][9]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0083",
    step: 83,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a1[3,82][9]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->f447b02ec6c7",
    tag: "e0084",
    step: 84,
    from: "2b4bebd52c4e",
    to: "f447b02ec6c7",
    raw_action: "g0a2[8,83][9]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->f447b02ec6c7",
    tag: "e0085",
    step: 85,
    from: "f447b02ec6c7",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,84][9]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->ee8dc65b7068",
    tag: "e0086",
    step: 86,
    from: "f447b02ec6c7",
    to: "ee8dc65b7068",
    raw_action: "g0a4[2,85][9]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#53d644a7]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0087",
    step: 87,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,86][9]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0088",
    step: 88,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,87][9]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0089",
    step: 89,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,88][10]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0090",
    step: 90,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a7[5,89][9]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0091",
    step: 91,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a8[1,90][9]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->2b4bebd52c4e",
    tag: "e0092",
    step: 92,
    from: "ee8dc65b7068",
    to: "2b4bebd52c4e",
    raw_action: "g0a9[12,91][9]@MODEL_BACKg0s0[1,92][92]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0093",
    step: 93,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a0[4,92][10]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0094",
    step: 94,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a1[3,93][10]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->f447b02ec6c7",
    tag: "e0095",
    step: 95,
    from: "2b4bebd52c4e",
    to: "f447b02ec6c7",
    raw_action: "g0a2[8,94][10]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->f447b02ec6c7",
    tag: "e0096",
    step: 96,
    from: "f447b02ec6c7",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,95][10]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->ee8dc65b7068",
    tag: "e0097",
    step: 97,
    from: "f447b02ec6c7",
    to: "ee8dc65b7068",
    raw_action: "g0a4[2,96][10]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#53d644a7]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0098",
    step: 98,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,97][10]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0099",
    step: 99,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a7[5,98][10]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0100",
    step: 100,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a8[1,99][10]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->2b4bebd52c4e",
    tag: "e0101",
    step: 101,
    from: "ee8dc65b7068",
    to: "2b4bebd52c4e",
    raw_action: "g0a9[12,100][10]@MODEL_BACKg0s0[1,101][101]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0102",
    step: 102,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a0[4,101][11]@MODEL_SCROLL_BOTTOM_UPclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->2b4bebd52c4e",
    tag: "e0103",
    step: 103,
    from: "2b4bebd52c4e",
    to: "2b4bebd52c4e",
    raw_action: "g0a1[3,102][11]@MODEL_SCROLL_TOP_DOWNclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "2b4bebd52c4e-->f447b02ec6c7",
    tag: "e0104",
    step: 104,
    from: "2b4bebd52c4e",
    to: "f447b02ec6c7",
    raw_action: "g0a2[8,103][11]@MODEL_SCROLL_LEFT_RIGHTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=14][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->f447b02ec6c7",
    tag: "e0105",
    step: 105,
    from: "f447b02ec6c7",
    to: "f447b02ec6c7",
    raw_action: "g0a3[10,104][11]@MODEL_SCROLL_RIGHT_LEFTclass=androidx.viewpager.widget.ViewPager;resource-id=net.gsantner.markor:id/view_pager;enabled=true;scrollable=true;[P=6][T=0][][S=1.000000][RN=1][0,0,1080,2148][]"
  },
  {
    id: "f447b02ec6c7-->ee8dc65b7068",
    tag: "e0106",
    step: 106,
    from: "f447b02ec6c7",
    to: "ee8dc65b7068",
    raw_action: "g0a4[2,105][11]@MODEL_CLICKclass=android.widget.ImageButton;resource-id=net.gsantner.markor:id/next;enabled=true;clickable=true;[P=22][T=0][][S=1.000000][RN=1][915,1986,1047,2118][#53d644a7]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0107",
    step: 107,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a5[7,106][11]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0108",
    step: 108,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a6[6,107][11]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/title;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=1][0,66,1080,433][Share ->]"
  },
  {
    id: "ee8dc65b7068-->ee8dc65b7068",
    tag: "e0109",
    step: 109,
    from: "ee8dc65b7068",
    to: "ee8dc65b7068",
    raw_action: "g0a7[5,108][11]@MODEL_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=22][T=0][][S=1.000000][RN=1][0,1350,1080,1900][]"
  },
  {
    id: "ee8dc65b7068-->f441effa616e",
    tag: "e0110",
    step: 110,
    from: "ee8dc65b7068",
    to: "f441effa616e",
    raw_action: "g0a8[1,109][11]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;enabled=true;clickable=true;long-clickable=true;[P=6][T=0][][S=1.000000][RN=2][425,1350,1080,1900][Manage y]"
  },
  {
    id: "f441effa616e-->ee8dc65b7068",
    tag: "e0111",
    step: 111,
    from: "f441effa616e",
    to: "ee8dc65b7068",
    raw_action: "g0a9[12,110][11]@MODEL_BACKg0s0[1,111][111]net.gsantner.markor.activity.IntroActivity@471443323@Naming[0]@[W=5][A=10][P=8][T=0][]"
  }
];
