# `FNX_PF_RING_SM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

all-cards split engine の prompt prefill で、カード間の chunk sum に使う ring を選びます。既定では page-locked host memory 上の copy-engine ring を使います。`FNX_PF_RING_SM` が非 0 のときは別の ring を割り当て、各カードの GPU thread が読み書きする旧経路を選びます。この設定は decode ring ではなく prompt prefill の経路に作用します。

## 値と判定

`env_int("FNX_PF_RING_SM", 0) != 0` で判定します。`env_int` は環境値全体を base 10 の `long long` として解析し、未設定なら既定値を返します。符号（`+` / `-`）は許可され、値が 0 以外なら有効です。

| 環境値 | 判定・結果 |
|---|---|
| 未設定 | 既定値 `0`。copy-engine ring を使う |
| `0`, `+0`, `-0` | 無効。copy-engine ring を使う |
| `1`, `-1`, `2` など範囲内の非 0 整数 | 有効。GPU-thread ring を使う |
| 空文字、空白を含む値、整数以外、末尾に余分な文字がある値、`long long` 範囲外 | `runtime_error`。設定を無視して続行する fallback はない |

先頭・末尾の空白や小数表記は受け付けません。たとえば ` 1`、`1 `、`1.0`、`1x` は無効です。値域として 0/1 だけに制限する検査はないため、範囲内の任意の非 0 整数が有効です。

## 有効になる条件

この変数を読むのは `src/split/src/prefill.cu` の all-cards split engine のみです。Strata の通常エンジン全般に適用される設定ではありません。split engine 自体は CMake の `STRATA_BUILD_SPLIT` が既定 OFF で、Linux の CUDA または HIP 向けの別実行ファイル `strata-split-N` としてビルドされます。実行時にも Strata がその split engine を選択して起動した場合に限り、この変数が使われます。

選択される方式は値に加えて、prefill が実行され、その buffer の初期化が完了することを前提にします。別の環境変数 `FNX_PF_OVERLAP` は `ring_sm` が false のときだけ overlap を有効化できます。`FNX_PF_RING_SM` を非 0 にした経路では `p->overlap` は false となり、overlap 用 ring stream / event を作成しません。CLI 引数や設定値によるこの環境変数の上書きは見つかりません。

## 実行時の詳細

`Engine::prefill_alloc()` の中でカードごとの prefill state `Pf` を作る際に値を読み、`ring_sm` に保存します。非 0 の場合は既存の decode ring 設定を引き継いだうえで、prompt 用に `f32=false`、行数 `pf_c_` とし、`in`・`ag`・`flags` の buffer を割り当てます。値の判定結果は `Pf` に保持されるため、この初期化後に環境値を変えても、すでに作られた prefill state の方式は切り替わりません。`static` cache はありません。

prefill の attention 側の和と FFN 側の和で `ring_sm` が true なら `ring_sum(...)` を呼びます。false なら `FNX_PF_OVERLAP` が有効な場合は非同期経路、そうでなければ通常の `pf_ring(...)` 経路です。`src/split/src/prefill.cu` の実装コメントは既定 copy-engine path と `FNX_PF_RING_SM=1` の GPU-thread ring を区別しています。`docs/SPLIT_ENGINE.md` は両方式の回答比較として 61 件中 39 件が同一だったと記していますが、これは同資料の対象条件に限る記述で、ここでは独立に再測定していません。

不正な値では `parse_whole` の失敗により `FNX_PF_RING_SM: '<値>' is not a whole number` という例外になります。`sfnx` 実行ファイルでは最上位の例外処理が stderr に `sfnx: <例外内容>` を出して終了コード 1 を返します。Strata launcher の通常の fallback 規則は split engine 起動失敗時に通常の layer split で起動することですが、この不正値が起動時検査で先に報告されるか、選択後に子プロセスで発生するかは経路によります。少なくとも不正値を 0 として扱う実装ではありません。

## 根拠

- `src/split/src/env.hpp:15-22,33-40`: 符号付き十進整数の全体 parse、空・不正文字列・範囲外時の例外、未設定時の default。
- `src/split/src/prefill.cu:335-339,625-638,738-745`: `Pf` の `ring_sm`、カードごとの初期化時の読み取り、非 0 時の prompt ring 設定と buffer 割り当て。
- `src/split/src/prefill.cu:821-830,1241-1247,1299-1306`: overlap 条件と attention / FFN sum の ring 分岐。
- `src/split/src/engine.cu:274-276`: engine 初期化から `prefill_alloc()` を呼ぶ位置。
- `src/split/tools/sfnx.cpp:1040-1048`: `sfnx` の stderr 例外報告。
- `strata_cli/launch/runner.py:693-697,1630-1649`: split engine 選択経路と、明示 env dict がない場合に launcher 環境を子プロセスへ渡す箇所。
- `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:92-123`: split engine が opt-in build で CUDA/HIP 個別ターゲットとなること。
- `docs/SPLIT_ENGINE.md:3-5,37-48,77`: all-cards split の用途、開始条件、起動失敗時の fallback、GPU-thread ring との比較記載。
