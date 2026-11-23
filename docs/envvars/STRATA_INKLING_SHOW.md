# `STRATA_INKLING_SHOW`

調査対象: Strata main の HEAD 73d4f4196c25a65e02f6b9ef25d354826ce55105（2026-11-23 時点）。

## 役割

terminal/tools/strata_mcp.py の Strata.inkling_visible() が Inkling-2-Mini を MCP 管理サーバーのモデル一覧に含めるか判定するときに読む表示用フラグである。値が正確に 1 なら、Inkling の配布元が見つからずローカルファイルもなくても可視判定を通す。ダウンロード元の設定やモデルファイルを作る変数ではなく、Strata の推論処理やエンジンの選択を変更する読み取りは見つからない（terminal/tools/strata_mcp.py:657-664, 641-644）。

この判定が true で、読み込んだ setup.py に INKLING_FAMILIES があれば、tables() がその family を MCP の family 表へ追加する。strata_models は非 macOS 経路でその表をモデル一覧に使う。tools/list の strata_install の family 選択肢にも反映される（terminal/tools/strata_mcp.py:623-644, 2354-2363, 2417-2428, 2244-2259）。setup.py の import に失敗して組み込み fallback 表になると、Inkling family の表がないため、このフラグだけでは一覧に追加されない（terminal/tools/strata_mcp.py:600-627）。

## 値と判定

値は os.environ.get("STRATA_INKLING_SHOW") == "1" で比較され、文字列全体が大文字小文字も含めて 1 と一致するかだけを見る。数値変換、trim、前方一致は行わない。フラグが false の場合も、次の配布元またはファイルの判定が続く（terminal/tools/strata_mcp.py:657-662）。

| 条件 | unset | 有効になる値（フラグ単体） | 無効になる値（フラグ単体） |
|---|---|---|---|
| inkling_visible() が実行され、strata_control.inkling_family の import に成功 | 1 との比較は false。その後、配布元とローカルファイルを確認 | 1（完全一致） | 空文字、0、true、TRUE、スペース付き1、1の後ろに文字。いずれも後続条件を満たせば可視になる |

空文字と未設定はフラグ判定上どちらも false。値の境界は完全一致のみで、それ以外の文字列を拒否するエラーや警告はない。CLI 引数による上書きや、別変数との優先順位規則はこのフラグ自体にはない。STRATA_INKLING_SOURCE 等の配布元がある場合や所定のローカルファイルがある場合は、フラグの値にかかわらず可視になる（terminal/tools/strata_mcp.py:657-662, terminal/strata_control/inkling_family.py:121-139, 193-207）。

## 有効になる条件

- terminal/tools/strata_mcp.py の MCP 管理サーバー経路で inkling_visible() が呼ばれること。Strata の本体サーバーや GPU backend がこの名前を読む実装は確認できない（terminal/tools/strata_mcp.py:657-664）。
- strata_control.inkling_family の import が成功すること。import は環境変数判定より先で、例外が起きると except Exception が false を返すため、STRATA_INKLING_SHOW=1 でも可視にならない（同 :657-664）。
- MCP 表に family を出すには、setup_module() が INKLING_FAMILIES を持つ setup.py を読み込めること。読み込めない場合は fallback 表へ切り替わり、その表にはこの family がない（同 :600-627, 641-644）。
- フラグが正確に 1 でないときは、Inkling の sources() が非空、または設定された data directory の models/inkling-2-mini に local_files() が認識するファイルがあることでも可視になる。sources() は STRATA_INKLING_SOURCE と同梱 inkling-sources.json を含めて調べる。local_files() は登録済みファイル名とバイト数が一致する通常ファイルを数える（terminal/strata_control/inkling_family.py:121-139, 193-207; data directory は terminal/tools/strata_mcp.py:779-793）。
- macOS では model_table() と recommend() が macOS 専用経路へ分岐するため、strata_models のモデル一覧・推薦にこの Inkling 表示判定は適用されない。MCP の tool definition は別途 tables() を使う（terminal/tools/strata_mcp.py:1418-1425, 1522-1525, 1350-1372, 2354-2356）。

## 実行時の詳細

環境変数を読むのは inkling_visible() の呼び出し時で、関数内 static や属性への保存はない。tables() から呼ばれる own_families() と、非 macOS の model_table()・推薦処理から複数回呼ばれ得るため、プロセス内の os.environ が後で変更された場合は後続呼び出しで再評価される（terminal/tools/strata_mcp.py:623-644, 657-664, 1418-1425, 1522-1525）。

可視になると MCP のモデル family 表へ Inkling family の説明情報が追加され、strata_models では family のサイズ・ダウンロード量・適合情報などが返される。対応する family は strata_install の選択肢にも含まれる。モデル候補の提示・推薦はハードウェアやOS別の別処理を通るため、可視判定だけでインストールや実行が行われるわけではない（terminal/tools/strata_mcp.py:641-644, 1394-1416, 2244-2260, 2417-2433）。

inkling_visible() 内で import、配布元確認、ファイル確認などの例外が発生した場合は捕捉され、可視判定は false になる。この except 節はログを出さない。例外が後続の MCP 処理へ伝播しないため、この判定自体によるエラー応答やサーバー終了もない（terminal/tools/strata_mcp.py:657-664）。通常時も、この変数の値に関するログ出力はない。

## ログと測定値

対象変数に関するログ出力・測定値はない。Inkling 可視判定内の例外は握りつぶして false にする（terminal/tools/strata_mcp.py:657-664）。MCP 呼び出しの応答では strata_models の family 一覧や推薦に反映されるが、macOS 専用モデル表・推薦には反映されない（同 :1350-1372, 1418-1425, 1522-1525, 2417-2433）。

## 根拠

- terminal/tools/strata_mcp.py:600-627 — setup.py の import と fallback 表。
- terminal/tools/strata_mcp.py:629-664 — family 表への追加と環境変数を含む可視判定。
- terminal/tools/strata_mcp.py:779-793 — 設定ファイルからの data directory 解決。
- terminal/tools/strata_mcp.py:1350-1372, 1418-1425, 1522-1525 — macOS 経路とモデル表・推薦の分岐。
- terminal/tools/strata_mcp.py:2244-2260, 2354-2363, 2417-2433 — MCP tool definition と strata_models の応答。
- terminal/strata_control/inkling_family.py:121-139, 193-207 — 配布元とローカルファイルの判定。
