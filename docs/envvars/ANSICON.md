# `ANSICON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の Python CLI が Windows の端末を旧式コンソールとして扱うかを判定する材料の一つです。`ANSICON` が truthy なら旧式コンソールではないと判定します。この判定は monitor の自動 glyph 選択とクラシック表示処理、および launcher の Unicode glyph 判定に影響します。ANSICON 自体の外部実装の動作を Strata が呼び出す箇所はありません。

## 値と判定

| 状態 | `legacy_console()` での扱い |
|---|---|
| 未設定 | 偽（この変数単独では旧式コンソール判定を妨げない） |
| 空文字 | 偽（`env.get()` の結果が空文字で truthy ではない） |
| 空でない任意の文字列 | 真として扱われ、旧式コンソール判定を妨げる。`"0"` も例外ではない |

値の数値変換、文字列比較、大小文字変換はありません。`env` は `os.environ` そのもので、値の読み取りは `legacy_console()` の呼び出し時です。設定変更を検出する独自の cache はこの関数にはありません。一方、`classic_style()` が初回呼び出しで計算した結果はモジュール変数 `_cached` に保存され、以後は再計算されません。

## 有効になる条件

- `legacy_console()` は先に `STRATA_GLYPHS` を `strip().lower()` して判定します。`ascii`、`legacy`、`solid` なら `ANSICON` を確認する前に旧式コンソールを真とし、`unicode` なら偽とします。それ以外（未設定・空文字を含む）は通常の判定へ進みます。
- 通常判定では `os.name != "nt" and sys.platform != "win32"` の場合に偽を返すため、通常の非 Windows 実行では `ANSICON` の有無は効果を持ちません。
- Windows の通常判定では `WT_SESSION`、`TERM_PROGRAM`、`ConEmuANSI`、`ANSICON` のいずれかが truthy、または `TERM` が `xterm`、`screen`、`tmux`、`vt` のいずれかで始まると旧式コンソール判定は偽になります。
- 対話型 `strata monitor --glyphs auto` では `choose_glyphs()` が `ANSICON` を含む判定を使います。明示的な `--glyphs`（`auto` 以外）は glyph 選択を先に確定するため、この自動判定を通りません。ただし monitor の classic style、余白、案内表示の判定は別途 `legacy_console()` を呼ぶため、明示指定でも影響します。
- `strata launch` の launcher widgets は `unicode_ok()` から同じ判定を使います。`STRATA_GLYPHS=ascii|legacy|solid` は旧式コンソール経路を強制します（widgets の ASCII 強制は `ascii|legacy`）。`STRATA_GLYPHS=unicode` は旧式コンソール経路を無効にします。

## 実行時の詳細

旧式コンソール判定が偽なら monitor は通常の Unicode/ASCII 選択へ進み、`classic_style()` による旧式向け処理は呼ばれません。したがって、`ANSICON` が非空で他の条件も通常判定を妨げない場合、Strata は classic style の適用、そこに含まれるフォント切り替え処理、および monitor の classic 用 margin と案内表示を使いません。自動 glyph 選択は `TERM=dumb` または出力 encoding がない場合には ASCII、それ以外では Unicode の graph glyph を encoding に対して試し、encoding 不可なら ASCII を選びます。これは Strata の選択処理についての記述で、実際に端末が glyph を描画できる保証ではありません。

`ANSICON` による警告、エラー、終了・失敗経路や、この判定経路からの専用ログ出力は見つかりません。Strata の資料 `docs/TERMINAL_LAUNCH.md:168` は `STRATA_GLYPHS` による見た目の強制と Windows Terminal 等では旧式表示を適用しないことを説明していますが、`ANSICON` の判定条件までは記載していません。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:35`。
- 環境値の取得、`STRATA_GLYPHS` の優先分岐、OS 判定、`ANSICON` を含む端末環境の条件: `strata_cli/consoleinfo.py:24-35`。
- classic style の初回計算・cache とフォント切り替え経路: `strata_cli/consoleinfo.py:158-178`。
- monitor の `--glyphs` 選択肢と既定値: `strata_cli/monitor_commands.py:49-60`。明示 glyph 指定の優先、旧式コンソール時の選択、encoding fallback: `strata_cli/monitor.py:26-45`。
- monitor 初期化時の classic style、margin、案内表示: `strata_cli/monitor.py:138-143,250-255`。
- launcher widgets の旧式コンソール判定と Unicode 可否の結果: `strata_cli/launch/widgets.py:43-57`。
