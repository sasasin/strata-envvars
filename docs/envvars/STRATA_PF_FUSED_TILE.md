# `STRATA_PF_FUSED_TILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

ネイティブ fused prompt-expert カーネルの routed-row tile を固定する内部調整値。値 `64` は work width `ww=4`（64 routed rows）、`128` は `ww=2`（128 routed rows）を選ぶ。未設定または他の値では、GPU・SM 数・expert あたりの routed rows・形式ペア等に基づく自動選択を使う。カーネルの選択・有効化自体は行わず、すでにこの native 経路を使う launch の tile 選択だけを変える（`engine/src/prefill/moe_fused_iq.cu:3327-3352, 3358-3374`）。

対象実装は CUDA/HIP の `moe_fused_iq.cu` で、OS 別の判定はなく、通常の native GGUF expert 経路のほか、Qwen3.6 用に同ファイルを別 namespace でコンパイルしたコピーにも同じ処理がある（`engine/src/prefill/moe_fused_iq_q36.cu:1-8, 33-37`）。SYCL の native fused 実装は stub であり、この環境変数を読む処理はない（`engine/sycl/src/prefill/moe_fused_stub.cpp:1-5`）。

## 値と判定

`forced_ww()` が `std::getenv` で値を取り、`std::atoi` の結果が整数 `64` なら `ww=4`、`128` なら `ww=2`、それ以外なら `0`（自動選択）にする。文字列全体の検証はしない。`atoi` の数値接頭辞が使われるため、先頭空白や符号の後に `64` / `128` があれば、後続文字を含んでも一致し得る（例: `"  +64x"`、`"128.0"`）。変換できない文字列は `0` になる。範囲検査やエラー報告はない。対象コードに CLI 引数や設定ファイルからこの値を上書きする経路はなく、`getenv` の値が判定元になる。

| 条件 | 未設定 | 固定 tile になる値 | 自動選択になる例 |
|---|---|---|---|
| `forced_ww()` を通る native launch | `0`（自動） | `64` 相当の `atoi` 結果で 64 rows、`128` 相当で 128 rows | 空文字、`0`、`1`、`true`、`false`、`64x` 以外の数値接頭辞など |

空文字は `getenv` 上は設定済みでも `atoi("") == 0` となるため自動選択。負数や `64` / `128` 以外の整数も自動選択になる。先頭の整数部分だけが使われるので `64x` は 64 rows を選ぶ。根拠: `engine/src/prefill/moe_fused_iq.cu:3328-3335`。

## 有効になる条件

- CUDA または HIP backend で `strata_pf_own` にこの翻訳単位が含まれ、対象のモデル・layer・形式ペアが native fused 経路に対応していること（`engine/cmake/backends/cuda.cmake:135-142`、`engine/cmake/backends/hip.cmake:30-44`、`engine/src/prefill/prefill.cpp:5830-5846`）。`STRATA_PF_FUSED_TILE` は native 経路を有効化しない。対応しない layer は fused 経路に入らず、通常の別経路を使う。native API 自体も未対応形式を検出すると stderr に `prefill fused experts (native): types %d / %d are not covered here` を出して終了する（`engine/src/prefill/moe_fused_iq.cu:3697-3700`）。
- native 経路が `launch_ww()` を使うこと。通常の launch はここで tile を選び、Qwen3.6 CUDA の追加 K-quant pair も同関数を通る（`engine/src/prefill/moe_fused_iq.cu:3864-3867`、`engine/src/prefill/moe_fused_iq_q36.cu:194-205`）。
- 自動選択時の既定は backend・GPU・launch により異なる。CUDA の規則は routed rows / expert の平均、SM class、SM 数、staging・形式ペアで 64/128 を選ぶ。HIP は同じ `pick_ww()` を通るが、CUDA 固有の staging fallback と Turing 分岐を通らない（`engine/include/strata/prefill/fused_tile_rule.hpp:49-106`、`engine/src/prefill/moe_fused_iq.cu:3358-3374`）。
- CUDA Turing (`sm_75`) では環境値も参照するが、64-row instance が形式に存在しない場合は `t75_ww()` が 128-row instance に置き換える（`engine/src/prefill/moe_fused_iq.cu:3233-3239, 3360-3366`）。
- `STRATA_PF_FUSED_NT=256` / `STRATA_PF_FUSED_WS=1` によって wide-batch kernel が選ばれる場合は `launch_ww()` より前に別経路へ戻るため、この値でその kernel の tile は変わらない（`engine/src/prefill/moe_fused_iq.cu:3855-3862`）。HIP の `P1A` / FP16 WMMA が条件を満たして早期 return する経路も対象外（`engine/src/prefill/moe_fused_iq.cu:3703-3714, 3716-3725`）。Qwen3.6 HIP の K-quant down pair 専用経路は `launch_ww()` を通らず、この値の対象外（`engine/src/prefill/moe_fused_iq_q36.cu:145-176`）。
- CUDA で staging kernel が使われ、staging 検査に失敗すると、指定値にかかわらず未 staging の 64-row kernel に切り替わる（Turing は staging 検査の対象外）。この fallback は HIP にはない（`engine/src/prefill/moe_fused_iq.cu:3280-3322, 3355-3373`）。

## 実行時の詳細

`forced_ww()` 内の function-local `static const int` が最初の呼び出し時に一度だけ値を読み、以後そのプロセスの当該翻訳単位では cache した判定を返す。起動後の環境変更は反映されない。Qwen3.6 コピーは別 namespace の独立したコードなので、通常コピーとは別の static cache を持つ（`engine/src/prefill/moe_fused_iq.cu:3328-3335`、`engine/src/prefill/moe_fused_iq_q36.cu:33-37`）。

強制値が認識されると `pick_ww()` はカード・行数等による自動規則を呼ばずに戻る。自動規則を出力する `STRATA_PF_TILE_DEBUG=1` のログも、この強制値の経路では出ない（`engine/src/prefill/moe_fused_iq.cu:3336-3352`）。ただし CUDA staging fallback は強制値より優先する。staging 検査はプロセス内で最大 256 launch まで行い、最初の失敗後は以後の launch を未 staging に切り替える（`engine/src/prefill/moe_fused_iq.cu:3281-3321`）。

選ばれた `ww` は launch grid の計算に使われ、各 gate/up・down kernel に渡される（`engine/src/prefill/moe_fused_iq.cu:3864-3872, 3903-3948`）。tile の変更による性能差は実行条件に依存するため、この調査では新たな性能を主張しない。

## ログと測定値

この変数の値を読み取ったことや、強制 tile を選んだこと自体を示すログはない。自動規則の選択ログは `STRATA_PF_TILE_DEBUG=1` のときだけだが、強制値があると自動規則に進まない（`engine/src/prefill/moe_fused_iq.cu:3336-3352`）。

CUDA の staging 条件に合わない場合は、失敗理由を含む次の stderr 行を一度出し、終了せず当該 launch と以後の launch に未 staging kernel を使う（`engine/src/prefill/moe_fused_iq.cu:3298-3321`）。

```text
prefill fused experts (native): <理由>; this launch and every later one in this process take the unstaged kernel (same results, slower)
```

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:3327-3374` — 値の読み取り・変換、cache、自動規則への分岐、Turing と staging の処理。
- `engine/include/strata/prefill/fused_tile_rule.hpp:49-106` — 自動 tile 選択。
- `engine/src/prefill/moe_fused_iq.cu:3864-3872, 3903-3948` — 選択 tile から grid と kernel launch への伝播。
- `engine/src/prefill/moe_fused_iq_q36.cu:1-8, 33-37, 194-205` — Qwen3.6 用コピーと CUDA K-quant 経路。
- `engine/src/prefill/moe_fused_iq_q36.cu:145-176` — tile 選択を通らない HIP Qwen3.6 K-quant 専用経路。
