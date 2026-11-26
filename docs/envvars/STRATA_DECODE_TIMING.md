# `STRATA_DECODE_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の要求ごとの decode timing 診断ログを有効にする。値を見ているのはエンジンの serve 要求処理中で、decode の計測値を `stderr` に出す条件になる。変数自体は decode の計算や出力 token を選択・変更する分岐には使われていない。CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` に同じ設定有無判定がある（それぞれ `:21779`、`:11737`）。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` だけを判定する。したがって未設定だけが OFF で、空文字を含む設定済みの値はすべて ON。`1`、`0`、`true`、`false`、`0anything`、空文字、空白だけの値はいずれも同じ扱いであり、大小文字・数値妥当性・文字列全体は検査しない（CUDA/HIP: `engine/src/program/generate.cpp:21777-21779`、SYCL: `engine/sycl/src/program/generate.cpp:11735-11737`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP | OFF | 値を問わず設定済み。例: `1`, `0`, `true`, 空文字 | なし |
| SYCL | OFF | 値を問わず設定済み。例: `1`, `0`, `true`, 空文字 | なし |

## 有効になる条件

- serve 要求処理の decode 経路に入る必要がある。設定の読み取りとログ出力は両方のエンジン実装で serve の要求処理内にあるため、通常の非 serve CLI 生成ではこの設定を読み取らない（CUDA/HIP: `engine/src/program/generate.cpp:21767-21780`、SYCL: `engine/sycl/src/program/generate.cpp:11732-11738`）。
- その要求で decode window が 1 つ以上処理される必要がある。0 window の要求では `dec_timing && dec_windows > 0` が成立せず、decode timing の行は出ない（CUDA/HIP: `engine/src/program/generate.cpp:23352-23354`、SYCL: `engine/sycl/src/program/generate.cpp:12957-12960`）。
- GPU 段階の内訳行も必要なら、別変数 `STRATA_VERIFY_PROFILE` を設定して GPU プロファイル計測を有効にする必要がある。Verifier は同変数の設定有無で計測を開始するが、計測領域の確保に失敗するとプロファイルを無効化する。また `profile_report()` は計測が無効、または window がない場合は空文字を返し、decode timing 側は空のレポートを出力しない（CUDA/HIP: `engine/src/core/verify.cpp:1262-1275,3208-3210`、SYCL: `engine/sycl/src/core/verify.cpp:816-825,2006-2008`、serve 側: `engine/src/program/generate.cpp:23385-23390`、SYCL: `engine/sycl/src/program/generate.cpp:12969-12974`）。
- `--pipeline-windows` の処理では decode timing 行に加え、パイプライン関連の診断行もこの設定で出力される（CUDA/HIP: `engine/src/program/generate.cpp:22584-22616`、SYCL: `engine/sycl/src/program/generate.cpp:12627-12646`）。

## 実行時の詳細

`dec_timing` は要求処理内の関数ローカル `static const bool` であり、そのプロセスで当該行に初めて到達したときに環境を一度だけ読み込む。起動後でも初回評価より前の環境変更は反映されるが、初回評価後の変更は後続要求に反映されない。子プロセスへの転送や、この変数と CLI 引数の優先順位を扱うコードは読み取り箇所にない（CUDA/HIP: `engine/src/program/generate.cpp:21777-21779`、SYCL: `engine/sycl/src/program/generate.cpp:11735-11737`）。

設定が ON でも計測値の出力ゲートを通るだけで、既存の window 数・時間・キャッシュ等のカウンターを使って診断行を作る。通常経路では `adapt wait + verify + commit/emit + draft + adapt join + other` の要求平均を含む `strata decode timing:` 行を `stderr` に出す。`--pipeline-windows` の経路では同じ見出しの行を pipeline 用の内訳で出力する。各経路で値が未設定、または decode window がなければ行は出ない（CUDA/HIP: `engine/src/program/generate.cpp:23352-23380`、SYCL: `engine/sycl/src/program/generate.cpp:12957-12968`）。

## ログと測定値

ログは `stderr`。通常の要求では `strata decode timing: ...`、pipeline 経路では同じ接頭辞に続き `verify ... + commit/emit ... + draft ...` の形式で出る。GPU プロファイルが有効でレポートがある場合は `strata decode GPU stages (ms/window):...`、複数 stage では `strata decode GPU stages, stage N (ms/window):...` も出る（CUDA/HIP: `engine/src/program/generate.cpp:23352-23390`、SYCL: `engine/sycl/src/program/generate.cpp:12957-12974`）。

`docs/DETAILS.md:364-374` は `STRATA_DECODE_TIMING=1` と `STRATA_VERIFY_PROFILE=1` の組み合わせ、および serial/pipelined の表示内容を説明している。実装では `STRATA_DECODE_TIMING` は値が `1` かを判定せず、設定有無だけを見ている。資料は GPU profiling が decode を少し遅くすると記すが、ここでは独自の性能測定は行っていない。

## 根拠

- CUDA/HIP 系の読み取り・static cache: `engine/src/program/generate.cpp:21777-21779`
- SYCL 系の読み取り・static cache: `engine/sycl/src/program/generate.cpp:11735-11737`
- CUDA/HIP 系の要求ログ・GPU stage 行: `engine/src/program/generate.cpp:23352-23390`
- SYCL 系の要求ログ・GPU stage 行: `engine/sycl/src/program/generate.cpp:12957-12974`
- GPU プロファイルの有効化と空レポート条件: `engine/src/core/verify.cpp:1262-1275,3208-3210`、`engine/sycl/src/core/verify.cpp:816-825,2006-2008`
- 付属資料との照合: `docs/DETAILS.md:364-374`
