# `STRATA_VERIFY_NO_HOST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL verifier の窓内処理で、GPU の各レイヤー doorbell をホストが処理するかを切り替える。真と判定されると、通常のレイヤーごとの host service loop を通さず、window 全体の完了を待つ。部分常駐モデルでは GPU 側で expert を計画する `device_plan_` と組み合わせる必要があり、対象は Intel Arc の SYCL engine 経路である。CUDA/HIP engine にこの名前を読む実装はない。`engine/sycl/src/core/verify.cpp:2615-2638`、`engine/sycl/src/core/verify.cpp:151-154`。

`device_plan_` が有効な場合は expert の計画と grouped expert 実行を device 側に置く。さらに `STRATA_VERIFY_LEAN` が有効で後述の除外条件に当たらなければ、solo window の graph から doorbell publish/wait、plan copy、PCIe-share 等の node を省く。ソースは VRAM/mirror groups、combine、answers が同じ kernels/data を使うと記す。lean graph の有効条件は `engine/sycl/src/core/verify.cpp:1022-1031`、device plan 判定は `engine/sycl/src/core/verify.cpp:919-925`。

## 値と判定

この変数は数値 parse をしない。実装箇所ごとに判定が少し異なる。

| 読み取り経路 | unset / 空文字 | 設定値の判定 | 例 |
|---|---|---|---|
| `env_on()`（expert staging 分岐） | off | 先頭文字が `0` 以外なら on | `1`, `true`, ` 1` は on。`0`, `0anything` は off |
| `no_host_wants_device_plan()` / `arena_refuses_no_host()` と `static` 判定（window/serve） | off | 値全体が文字列 `"0"` と異なれば on | `1`, `true`, `false`, ` 0`, `00`, `0anything` は on。厳密な `0` だけ off |
| `B60 single layout` の制約確認 | 条件不成立 | 値全体が厳密に `"1"` であることを要求 | `1` のみ通過。`true` や `01` は不成立 |

`env_on()` は `getenv` の値が存在し空でなく、先頭 byte が `'0'` でないかを返すため、文字列全体・数値としての妥当性・大文字小文字・空白は検査しない（`engine/sycl/src/core/verify.cpp:151-154`）。他の主な判定は `strcmp(value, "0") != 0` で、文字列全体を比較する（`engine/sycl/include/strata/core/verify_env.hpp:16-18,26-29`; `engine/sycl/src/core/verify.cpp:1027,2620`; `engine/sycl/src/program/generate.cpp:5210,5510,5641`）。従って `0anything` は経路により off/on が分かれる。無効文字列を拒否する処理はない。

SYCL serve wrapper は `STRATA_VERIFY_NO_HOST=1` を既定値にし、環境変数があれば既定値を上書きする。空文字は container に渡さず未設定扱いにし、`0` は値のまま渡す（`engine/sycl/serve/strata-sycl.sh:13-16,31-43`）。setup の Alchemist/i915 経路は `0` を config に設定し、layer split で VRAM 不足が予想されユーザー config にこのキーがない場合も `0` を補う（`engine/sycl/setup_intel.py:414-425,546-559`）。

## 有効になる条件

- Strata の SYCL engine 経路で読む。該当名の実装参照は `engine/sycl` 配下にあり、CUDA/HIP engine の読み取りはない。
- `STRATA_VERIFY_DEVICE_PLAN` が未設定のとき、起動時判定 `no_host_wants_device_plan()` がこの変数を on とみなせば、engine は `STRATA_VERIFY_DEVICE_PLAN=1` を設定して理由を stderr に出す。`STRATA_VERIFY_DEVICE_PLAN` が `0` でも設定済みなら保持され、自動設定しない。後段の `device_plan_` は `atoi(value) != 0` で決まるため、例えば明示値 `0` や `false` は off（`engine/sycl/src/program/generate.cpp:1850-1856`; `engine/sycl/src/core/verify.cpp:919-925`）。
- すべての expert が VRAM 常駐の場合、`device_plan_` は `!all_resident_` 条件で off になる。NO_HOST が on でもこのケースでは欠落 expert の host fallback は不要で、全 window の完了待ち経路が使われる（`engine/sycl/src/core/verify.cpp:897-925,2615-2638`）。
- NO_HOST と device plan が on でも、`--stream-experts` を使わず host expert arena を使い、VRAM cache に全 expert が入らない場合は起動時に拒否される。`--stream-experts` の pinned mirror 経路または全 expert の VRAM 常駐が必要（`engine/sycl/src/program/generate.cpp:5193-5203`; helper 条件は `engine/sycl/include/strata/core/verify_env.hpp:21-29`）。
- stream/mirror 経路でも VRAM 外かつ mirror にない expert があると拒否される。integrated GPU の UMA pool では専用の「model does not fit」拒否が先行する。複数 GPU の layer split では後続 stage の欠落 expert を拒否する。いずれもホストが代わりに応答しないため（`engine/sycl/src/program/generate.cpp:5508-5532,5636-5653`）。
- 欠落 expert がある状態で adaptive swaps が指定され、SYCL mirror adaptive cache が使われない場合、swap 対象が VRAM/mirror のどちらにもなくなるのを避けるため `--adapt-every` の実行時値を 0 にし、stderr に理由を出す（`engine/sycl/src/program/generate.cpp:5534-5541`）。
- `STRATA_SYCL_MIRROR_ADAPT` が `1` で始まる値（例: `1`, `10`, `1abc`）の場合も `device_plan_` と NO_HOST 判定の両方が必要。不成立なら verifier 初期化時に `mirror adaptive expert usage requires NoHost device planning` の例外を投げる（別変数の読み取りは `engine/sycl/src/core/verify.cpp:75-80`、条件と例外は同:977-983）。
- `STRATA_VERIFY_LEAN` による node 省略は、未設定・空文字・先頭文字が `0` 以外の値で同変数が有効で、NO_HOST・device plan も有効、かつ batch window、step hooks、remote optimization、always-publish、stepped mode のいずれでもない場合に限る。`STRATA_VERIFY_LEAN=0` または `0anything` で無効になり、batch は doorbell node を保持する（`engine/sycl/src/core/verify.cpp:1022-1031`）。
- staged native expert 経路は加えて `STRATA_SYCL_EXPERT_STAGE` が `env_on()` 判定で on（未設定・空・`0` 始まり以外）、`gy == 0`、Battlemage layout ではないことが条件（`engine/sycl/src/core/verify.cpp:1732-1749`）。
- B60 single layout は serve、native pack、single device 等の複数条件に加え、この変数と `STRATA_VERIFY_DEVICE_PLAN` の両方を厳密に `1` にする必要がある（`engine/sycl/src/program/generate.cpp:4591-4597`）。

## 実行時の詳細

通常の SYCL serve は wrapper の既定 `STRATA_VERIFY_NO_HOST=1` と `STRATA_VERIFY_DEVICE_PLAN=1` を engine に渡す。config/env などから外部環境に同名の値が渡れば wrapper の既定値を上書きする。`setup_intel.py` は i915 用 config に `0` を設定し、layer split で不足が予測される場合にも未指定時だけ `0` を補う。CLI 引数そのものがこの変数を上書きする実装は見つからなかった（`engine/sycl/serve/strata-sycl.sh:31-43`; `engine/sycl/setup_intel.py:414-430,546-559`）。

engine 起動時に NO_HOST が on で `STRATA_VERIFY_DEVICE_PLAN` 未設定なら、後者を `1` に設定する。明示された `STRATA_VERIFY_DEVICE_PLAN=0` は尊重されるので、NO_HOST を on にしたまま device plan を無効にできる。この組合せでは欠落 expert の device plan は用意されない。plan の実際の有効化は verifier 初期化で環境値を `atoi` して決まる（`engine/sycl/src/program/generate.cpp:1850-1856`; `engine/sycl/src/core/verify.cpp:919-925`）。

window record と window wait はそれぞれ関数内 `static const` に NO_HOST 判定を保存するため、その関数が初めて評価された値を以降の呼び出しで使う。`env_on("STRATA_VERIFY_NO_HOST")` の expert staging 判定は helper を呼ぶたび環境を読む。通常の実行では起動後に環境を書き換える運用は想定されておらず、static 判定は変更を反映しない（`engine/sycl/src/core/verify.cpp:1026-1031,1736-1738,2620,2636-2638`）。

NO_HOST の window wait 経路では per-layer doorbell loop を飛ばし、全 window graph の完了を待つ。NO_HOST が off の経路ではレイヤーごとに GPU の ring を待ち、host が payload を処理する。staged native expert 実行は別条件で有効化でき、batch/device-plan/window の制約に従う（`engine/sycl/src/core/verify.cpp:2613-2645,1736-1749`）。

## ログと測定値

- device plan を自動設定したとき: `strata: STRATA_VERIFY_NO_HOST=1 needs the device-built plan for experts outside VRAM: STRATA_VERIFY_DEVICE_PLAN=1 is set too (STRATA_VERIFY_DEVICE_PLAN=0 keeps it off)`（`engine/sycl/src/program/generate.cpp:1850-1856`）。
- host arena に不足 expert があると `strata generate: REFUSED: STRATA_VERIFY_NO_HOST=1 with the host expert arena (no --stream-experts): the VRAM cache holds %lld of %lld experts and nothing answers for the rest, so replies come out as garbage ('!' x N, #4698) or the window hangs. Use --stream-experts (its pinned mirror is read by the device plan), or set STRATA_VERIFY_NO_HOST=0 where the card runs the arena (an i915 card)` を stderr に出し、`refuse_exit(2)` で終了する（`engine/sycl/src/program/generate.cpp:5195-5203`; `refuse_exit` は指定 code で `_Exit`、同:1803-1812）。
- mirror 不足では `strata generate: REFUSED: %lld experts are neither in VRAM nor mirrored; with STRATA_VERIFY_NO_HOST the device plan cannot run them and generation would lack a safe host fallback - raise STRATA_MIRROR_MIB or the free RAM, or lower --max-context`、layer split の後続 stage 不足では `strata generate: REFUSED: %lld experts of the later layer-split stages are neither in VRAM nor mirrored (the host mirror covers the first stage only); with STRATA_VERIFY_NO_HOST the device plan cannot run them and the card is lost at the first verify window - set STRATA_STAGE_TRIM=1 (with --layer-split N) to free each card's duplicate dense weights, lower --max-context or --vram-reserve-mib, or unset STRATA_VERIFY_NO_HOST` を出し、同じく code 2 で終了する（`engine/sycl/src/program/generate.cpp:5528-5532,5647-5653,1803-1812`）。UMA pool 不足にも個別の `REFUSED` がある（同:5511-5526）。
- adaptive swap を無効化した場合は `strata generate: adaptive swaps off: with STRATA_VERIFY_NO_HOST an expert they move out of VRAM would be neither there nor mirrored` と出る（`engine/sycl/src/program/generate.cpp:5537-5541`）。
- `docs/INTEL.md:45` は値 `0` が wrapper から渡されないと説明するが、現行 wrapper は空文字だけを除外し `0` を渡し、engine の判定も値を検査する。ソース実装を現行挙動の根拠とした。測定値は記載しない。

## 根拠

主要な読み取りと処理: `engine/sycl/src/core/verify.cpp:75-80,151-154,977-983,1022-1031,1732-1749,2613-2638`; `engine/sycl/include/strata/core/verify_env.hpp:16-29`; `engine/sycl/src/program/generate.cpp:1850-1856,5193-5203,5210-5214,5508-5541,5636-5653`; wrapper/setup の既定・転送: `engine/sycl/serve/strata-sycl.sh:13-16,31-43`, `engine/sycl/setup_intel.py:414-430,546-559`。

