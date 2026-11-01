# `DS4_TRACE_DISP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリは `main` で、作業ツリーは clean（`## main...origin/main`）。

## 役割

DeepSeek の Metal engine が、実行中の layer と Metal dispatch、deferred command buffer の flush を stderr に記録する診断用スイッチです。モデル計算や dispatch の選択を変える処理はありません。

## 値と判定

値の文字列や数値は parse せず、`getenv()` が null pointer かどうかだけを見ます。したがって未設定なら無効、空文字を含む何らかの値が設定されていれば有効です。`0`、`false`、任意の文字列も有効です。CLI 引数や別の環境変数による上書き・優先順位はありません。

| 出力 | 判定方法 | 環境変更の反映 |
|---|---|---|
| `TRACE flush_runs (...)` | `flush_runs()` を呼ぶたびに `getenv(...)` を評価し、設定済みかつ deferred command buffer がある場合に出力 | 次の呼び出しから反映 |
| `TRACE disp ...` | Metal runtime の対象 dispatch 経路で、関数内 `static const bool` を初期化 | 最初にこの判定へ到達した時点で固定 |
| `TRACE layer ...` | `ds4_dbg("DS4_TRACE_DISP")` が layer ごとに環境を評価 | 次の layer 判定から反映 |

## 有効になる条件

- **Metal runtime**: `metal/CMakeLists.txt` は macOS 専用で、DeepSeek の `strata_ds4` に `STRATA_DS4_RUNTIME=1` の runtime と `STRATA_METAL=1` の定義を付けます。`DS4_TRACE_DISP` による全出力はこの Metal DeepSeek engine の経路です。
- **flush ログ**: `Context::flush_runs()` が呼ばれ、かつ `impl_->cb_def != nil` のときだけ出ます。flush が呼ばれても deferred buffer がなければこの行は出ません。
- **dispatch ログ**: `Context::run()` の deferred dispatch 経路、すなわち `ds.size() == 1 && reps == 1 && !barrier_between` の条件を通る dispatch が対象です。その他の run 経路ではこの `TRACE disp` 判定は実行されません。
- **layer ログ**: `ds4_model.cu` の `layer()` が呼ばれた場合が対象です。`ds4_dbg()` は `STRATA_METAL` build では環境変数の設定有無を返し、それ以外の build では常に false です。よって CUDA/HIP build ではこの helper 経由の layer ログは出ません。

## 実行時の詳細

`TRACE disp <kernel-name>` は dispatch 名を含む一行を stderr に出します。判定はその実行ファイル内で最初に対象経路へ到達した時に cache されるため、その後プロセス内で環境変数を変更しても、この出力の有効・無効は変わりません。

`TRACE layer <layer> p0=<position> T=<window-size>` は各 layer の `layer()` に入った際の layer index、window 開始位置、window token 数を stderr に出します。この箇所は helper が呼ばれるたびに `getenv()` するため、最初の判定後の環境変更も後続 layer の判定に反映されます。

`TRACE flush_runs (<queued-count> queued)` は `flush_runs()` の入口で、deferred buffer がある場合に queued dispatch 数を stderr に出します。ここも呼び出しごとに環境を確認します。いずれのログも出力や計算の失敗を表すものではなく、この環境変数自身による終了・fallback・警告経路はありません。

`docs/DEEPSEEK_MAC.md` は開発者向け診断一覧で `DS4_TRACE_DISP=1` を挙げています。ただし実装は `=1` を要求せず、設定有無だけを検査します。

## 根拠

- 全参照の検索では、候補一覧以外に `metal/src/mtl_rt.mm` の flush と dispatch、`src/dsv41/ds4_model.cu` の layer の計3箇所を確認しました。layer の参照は `src/dsv41/ds4_launch.h:30-36` の動的名前 helper に渡されます。
- 値判定・flush ログ: `metal/src/mtl_rt.mm:855-856`。
- dispatch 経路と cache、ログ: `metal/src/mtl_rt.mm:902-935`。
- helper の Metal / 非 Metal 分岐と値判定: `src/dsv41/ds4_launch.h:30-36`。
- layer ログ: `src/dsv41/ds4_model.cu:9961-9985`。
- macOS 専用 build と `strata_ds4` の compile definition: `metal/CMakeLists.txt:1-2,16-18,151-171`。
- 開発者向け診断一覧: `docs/DEEPSEEK_MAC.md:85-98`。
- 候補名の一覧掲載: `docs/envvars/000_envvers.md:322`。
