# `STRATA_DS4_DISK_SKIP_BUDGET`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek V4.1 エンジンの実験的な disk skip 自動制御で、低い route weight の expert を省略し続ける累積 token 数の上限を指定します。上限に達すると、その回答の途中でも disk skip を OFF にします。単独では skip を有効化しません。`STRATA_DS4_DISK_SKIP_W` が正で、さらに `STRATA_DS4_DISK_SKIP_AUTO` が 0 以外の場合にだけ、この予算が参照されます。

## 値と判定

| 環境変数の値 | `disk_skip_budget` |
|---|---:|
| 未設定 | 512 |
| 数値として読める値 | `atof` で float に変換し、`int` へ切り捨てた値。ただし最低 1 |
| 空文字、数値で始まらない文字列、0、負数 | 1 |

文字列全体の妥当性検査はありません。`atof` が数値の接頭部を読める文字列では、その接頭部を使います。たとえば `17.8tail` は変換可能な値域なら 17 になります。`std::max(1, ...)` により、変換後の 0 以下は 1 になります。int の範囲外や非有限値を `int` に変換した場合の結果は、この実装から保証できません。

CLI 引数や設定ファイルによる上書き箇所はなく、予算はモデルインスタンス初期化時に環境から読み取られ、そのインスタンスのメンバー値として保持されます。実行中に環境を書き換えても、そのインスタンスの予算は変わりません。

## 有効になる条件

- CMake の `STRATA_BUILD_DSV41` が有効で、`STRATA_HIP_GFX906` ではないビルドに含まれる `strata-dsv41` エンジンのコードです。CMake 上、このビルドオプションは既定で OFF です。
- 自動制御は `STRATA_DS4_DISK_SKIP_W > 0` かつ `STRATA_DS4_DISK_SKIP_AUTO` の `atof` 結果が 0 以外のときだけ有効です。`STRATA_DS4_DISK_SKIP_AUTO` は既定 0 です。
- 実際の disk skip は `STRATA_DS4_DISK_SKIP_W > 0`、非 MTP layer、かつ `STRATA_DS4_DISK_SKIP_FROM` 以上で trunk の `g.nl` 未満の layer に限られます。`STRATA_DS4_DISK_SKIP_FROM` は未設定時 0 です。
- 自動制御が無効なら、budget 値を読み取っても skip の停止制御には使われません。自動制御が有効な場合も、settle window の準備中や冷えた expert の割合が既定の停止条件を満たした場合は、budget より先に停止することがあります。

## 実行時の詳細

各対象 token・layer で、router が選んだ expert の route weight 合計に対し、weight が `STRATA_DS4_DISK_SKIP_W * 合計` より小さい expert を light と判定します。その expert が CPU lane にあり、かつページが RAM にないときは計算対象 `picks` に加えず、省略数を数えます。lookahead が先にページを読み込んで RAM に載せた expert はこの disk skip の対象になりません。これはモデルの計算結果を変える実験機能で、省略した expert の weight は再正規化されません。

自動制御中は layer ごとの重い routed expert と、そのうち CPU lane にあり cold と判定した expert を集計します。集計対象の開始 layer（`STRATA_DS4_DISK_SKIP_FROM`）で `since` に現在の window の token 数 `T` を加算し、`since >= disk_skip_budget` ならその時点で `skip_auto_off("its budget", ...)` を呼びます。したがって window が複数 token なら実際の停止判定は閾値をまたいだ window の処理後になります。

停止時は stderr に `ds4: DISK_SKIP auto: off after <tokens> tokens (its budget; cold share <share>, the lowest <low>)` 形式の行が出ます。自動制御の再開判定は CLI/サーバーの次 request 開始時です。直近に記録した CPU lane expert が 64 件以上あり、そのうち RAM に残るものが半数未満なら ON に戻して `since` を 0 にし、stderr に `ds4: DISK_SKIP auto: on again for request ...` を出します。64 件未満、または半数以上が RAM に残っていればその request では再開しません。

## 根拠

- `src/dsv41/ds4_model.cu:1352-1355,1441-1445` — 共通 helper `env_f` の `getenv` / `atof`、予算の既定値 512、int 変換、下限 1。メンバー初期化子でモデルインスタンスごとに値を保持します。
- `src/dsv41/ds4_model.cu:1391-1412,1427-1444` — 関連する weight・auto・開始 layer の既定値と、自動制御の設定条件。
- `src/dsv41/ds4_model.cu:1458-1488` — 自動制御の集計、予算比較、budget 到達時の stderr ログ、および先行する停止条件。
- `src/dsv41/ds4_model.cu:1492-1520`, `src/dsv41/ds4_main.cpp:1375,1845,2693` — request 間の再開判定と CLI/サーバーからの呼び出し。
- `src/dsv41/ds4_model.cu:9460-9518` — 対象 layer の条件、route weight 閾値、CPU lane/RAM 判定、省略と skip 統計。
- `CMakeLists.txt:931-945` — `strata-dsv41` の独立ターゲット、`STRATA_BUILD_DSV41` の既定 OFF、および gfx906 での除外。
