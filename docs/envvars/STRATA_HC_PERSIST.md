# `STRATA_HC_PERSIST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU verifier の hyper-connection read について、通常の multi-kernel 読み取りの代わりに、複数ブロック常駐と grid barrier を使う persistent kernel を選ぶ opt-in 変数。実装は `engine/src/kernels/cuda/fused_gr.cu` にあり、`Verifier::init` でカードごとの事前確認を行い、verify window の read 時に条件を満たすと切り替える。drafter 側や、この変数が呼ばれない通常の read 経路を切り替えるものではない（`engine/src/core/verify.cpp:968-969,1796-1818`、`engine/src/kernels/cuda/fused_gr.cu:4831-4838`）。

## 値と判定

`env_on()` は `std::getenv` の結果を `std::atoi` に渡し、変換値が 0 以外なら opt-in とする。未設定・空文字・先頭が数値でない文字列は 0 となり無効。`atoi` は文字列全体の厳密な数値検証ではないため、先頭の空白や符号は許容され、数値部分の後ろは判定に使われない（例: `" 1x"` は有効、`"0anything"` と `"true"` は無効）。負の非ゼロ値も有効。`dp_on()` は同じ環境変数を別に `atoi` し、変換値がちょうど 3 のときだけ double accumulation 用 kernel を選ぶ（`engine/src/kernels/cuda/fused_gr.cu:5136-5140,5156-5158`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA / HIP の persistent 実装がコンパイルされた場合 | 無効。通常 read に進む | `1`, `2`, `-1`, `1tail`。`3` は有効で、double accumulation kernel を選択 | 空文字、`0`, `0anything`, `true` |
| persistent 実装がないビルド経路 | 関数 stub が常に無効を返す | なし | すべて。`fused_gr_persist_init()` は空、read は `false`（`engine/src/kernels/cuda/fused_gr.cu:5318-5320`） |

数値の全体検証、上限・下限 clamp、無効文字列の警告はない。`atoi` の戻り値が 3 であること以外、非ゼロ値の大小で挙動は変わらない。CLI 引数や設定ファイルから値を上書きする読み取りは見つからなかった。

## 有効になる条件

- GPU engine の `fused_gr.cu` で CUDA または HIP コンパイラ向け persistent 実装が有効であること。その他のコンパイル経路では stub が常に通常 read への fallback を返す（`engine/src/kernels/cuda/fused_gr.cu:4839,5318-5320`）。
- `Verifier::init` 時に選択されている GPU が 0–63 の範囲で、warp size が 32 であること。wave64 では初期化を打ち切り、通常 read を使う（`engine/src/kernels/cuda/fused_gr.cu:5163-5175`）。
- HIP では gfx11 / gfx12 に該当しないこと。該当時は barrier timeout 用の `s_memrealtime` がないとして初期化を打ち切る（`engine/src/kernels/cuda/fused_gr.cu:5177-5182`）。CUDA 側にこの gfx 判定はない。
- ワークスペース確保と初期の結果確認に成功すること。起動時確認は token 数ごとに通常 read と比較し、許容差内で有限な結果になり、全 80 blocks が同時常駐できる範囲を `max_t` として記録する。初期化で確認できなかった token 数以上は通常 read に戻る（`engine/src/kernels/cuda/fused_gr.cu:5185-5194,5230-5280,5287-5301`）。
- 実 read の token 数が 1 以上かつ `max_t` 以下であること。HC Q8 (`q8_down` / `q8_up`)、HC REQ8 (`s_down` / `s_up`)、または QFUSE (`q8_mixed`) の引数がある read は persistent kernel を使わない（`engine/src/kernels/cuda/fused_gr.cu:5304-5316`）。
- この呼び出し箇所は verifier の hyper-connection read であり、persistent read の並行実行を避ける verifier 側の単一 stream を前提にする。drafter は通常 kernel を使用する（`engine/src/kernels/cuda/fused_gr.cu:4837-4838`）。

## 実行時の詳細

`Verifier::init` は現在の GPU に対して `fused_gr_persist_init()` を呼ぶ。`env_on()` の結果は関数内 `static` に一度保存されるため、最初の評価後にプロセス環境を変更しても反映されない。カードごとの `DevState::tried` も初期化試行後に立ち、同じカードでは再試行しない。`dp_on()` も別の関数内 `static` として最初の呼び出しで値を保存する（`engine/src/core/verify.cpp:956-970`、`engine/src/kernels/cuda/fused_gr.cu:5111-5119,5136-5140,5156-5169`）。

起動時確認に通ったカードでは、verify window ごとに `fused_gr_read_persist()` が環境値・token 数・Q8/QFUSE 引数を確認する。使わない場合は `false` を返し、呼び出し元が `fused_gr_read_multi()` を実行する。使う場合は persistent kernel を指定 stream に enqueue し、`true` を返して通常 read を省略する（`engine/src/core/verify.cpp:1816-1818`、`engine/src/kernels/cuda/fused_gr.cu:5304-5316`）。

この kernel は通常 read と異なる加算順序で計算するため bitwise 同一ではない。初期確認では最大相対差が `1e-4` 未満であることを採用条件とする。実行中の grid barrier は CUDA で約 2 秒相当、HIP で 2 秒相当の timeout を持ち、block が揃わないと kernel 内で中断する設計だが、実 read 時の barrier 中断をホスト側で検出して通常 read に再実行する分岐は、この呼び出し経路にはない（`engine/src/kernels/cuda/fused_gr.cu:5141-5149,4867-4908,5271-5279`）。

値 `3` は有効値の一つで、persistent kernel の部分 dot と二乗和の蓄積に double を使う variant を選ぶ。それ以外の非ゼロ値は float variant を選ぶ（`engine/src/kernels/cuda/fused_gr.cu:4864-4865,5136-5140,5156-5158`）。

## ログと測定値

初期化で wave size 不一致、HIP gfx11/gfx12、workspace 確保失敗、結果確認失敗、80 blocks 非常駐のいずれかになると、stderr に `strata hc: CUDA%d: STRATA_HC_PERSIST=1 is off here: ...` の理由行を出す。確認に通ると、stderr に `strata hc: CUDA%d: STRATA_HC_PERSIST=1: the verifier's hyper-connection read runs as one persistent kernel ...` と token 上限・timeout 数・通常 read との最大相対差を出す（`engine/src/kernels/cuda/fused_gr.cu:5172-5181,5191-5194,5287-5301`）。未設定または 0 なら `fused_gr_persist_init()` の先頭で戻り、persistent 用ログは出さない（`engine/src/kernels/cuda/fused_gr.cu:5163-5165`）。

`docs/AMD_HIP.md:520,811` と `docs/bench-results/2026-10-12-hc-persist-gfx1030/README.md:75-107` には RX 6900 XT 2 枚・ROCm 10.0 等での verify window 時間の測定が記載されている。ただしその計測資料は別の旧 commit `a0116b27` のコードに基づくため、本調査対象 commit の性能値としては扱わない。

## 根拠

- 読み取り、数値判定、cache、kernel variant: `engine/src/kernels/cuda/fused_gr.cu:5136-5140,5156-5158`
- 初期化と backend / GPU 条件・ログ: `engine/src/kernels/cuda/fused_gr.cu:5163-5194,5287-5301`
- verifier の初期化と実 read fallback: `engine/src/core/verify.cpp:956-970,1796-1818`
- persistent read 選択条件: `engine/src/kernels/cuda/fused_gr.cu:5304-5320`
- verifier 専用・計算特性・barrier: `engine/src/kernels/cuda/fused_gr.cu:4831-4839,4867-4908`
