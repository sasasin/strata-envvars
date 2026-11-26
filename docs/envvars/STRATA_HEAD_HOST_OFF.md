# `STRATA_HEAD_HOST_OFF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU VRAM が足りないときに、Strata の native output head を mapped pinned host memory へ自動で移す経路を止める。名前に `OFF` が付くが、値を parse するフラグではなく、環境変数が存在するだけで抑止される。設定すると、head を VRAM に置けず cache 用の空きもない場合に自動退避による起動継続を試さず、VRAM 不足の経路を維持する。

対象は `NativeHead` が扱う `output.weight` であり、一般の全モデル weight を host に移す設定ではない。コード上の参照は `engine/src/core/native_head.cpp` の upload fallback と `engine/src/program/generate.cpp` の cache 計画時の単一 GPU・layer split の自動退避である。環境変数名の実参照はこの 3 か所で、`terminal/data/settings-register.json` にも名前の登録があるが、そこは engine の読み取り処理ではない。

## 値と判定

3 か所とも `std::getenv("STRATA_HEAD_HOST_OFF") == nullptr` を条件にしている。値の内容は読まず、文字列変換・大文字小文字比較・空白除去・数値妥当性検査もない。実行中に各分岐へ到達した時点で環境を直接確認し、`STRATA_HEAD_HOST_OFF` 自体の static cache はない。

| 条件（build など） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 全ての読み取り箇所 | 自動退避が他条件を満たせば許可される | なし（退避を許可する値はない） | 空文字、`0`、`1`、`false`、`true`、任意の文字列。いずれも変数が存在するため自動退避を抑止 |

## 有効になる条件

- native head の初回 VRAM upload fallback は、`cudaMalloc` が失敗し、GPU 情報を取得できて discrete GPU と判定され、Metal build でも integrated GPU でもなく、`STRATA_Q6_PACKED` による packed Q6_K head が有効でない場合に候補となる。この条件で本変数が設定済みなら pinned host memory への upload fallback を試さない。`STRATA_HEAD_HOST` が設定されて明示的に host 配置を要求した場合も、実装上は同じ `STRATA_HEAD_HOST_OFF` 条件を通るため、本変数があるとその host 配置を完了できず upload エラーになることがある。参照: `engine/src/core/native_head.cpp:130-135,222-252`、`engine/include/strata/core/spill_gate.hpp:8-14`。
- 単一 GPU の cache 計画時の退避は、cache slot が 0、native head がロード済みでまだ host 上ではない、`--vram-reserve-mib` が明示されていない、multi-GPU でなく layer stage がなく、`STRATA_SPILL_OFF` も未設定、かつ discrete GPU の条件を全て満たした場合だけ試す。`STRATA_HEAD_HOST_OFF` はこの自動退避を止める。参照: `engine/src/program/generate.cpp:9346-9353`。
- layer split では、head を持つ最終 stage の room が working cache の必要量より少なく、head が loaded かつ VRAM 上、`--vram-reserve-mib` が未指定、`STRATA_SPILL_OFF` が未設定、discrete GPU の条件を満たす場合に退避を試す。本変数の設定でこの処理を飛ばす。参照: `engine/src/program/generate.cpp:9903-9910`。
- Metal build と integrated GPU は `spill_allowed` が false となるため、cache 計画時の host spill は許可されない。single GPU の gate は GPU 情報の取得に失敗した場合も false となる。参照: `engine/include/strata/core/spill_gate.hpp:8-14`、`engine/src/program/generate.cpp:326-339`。
- `STRATA_SPILL_OFF` は cache 計画時の後二つの spill 経路を止めるが、upload 時の `native_head.cpp` fallback 条件には含まれない。`STRATA_HEAD_HOST` は upload 時に host を要求する別変数だが、本変数が設定されている場合の抑止を上書きしない。`STRATA_Q6_PACKED=1` で packed Q6_K head が有効な場合は、upload fallback 自体が除外され、`NativeHead::to_host` も packed Q6_K を移動しない。参照: `engine/src/core/native_head.cpp:130,222-225,262-265,297-300`、`engine/src/kernels/cuda/native_mmvq.cu:3145-3151`。
- `--vram-reserve-mib` を明示すると cache 計画時の二つの自動退避は抑止される。upload fallback は cache 計画より前の native head load にあるため、この CLI 条件とは別である。参照: `engine/src/program/generate.cpp:8382-8400,9350,9905-9907`。

## 実行時の詳細

通常の single GPU 経路では native head を expert cache 計画より先に読み込む。`NativeHead::load` は `STRATA_HEAD_HOST` の有無を調べ、未設定なら `cudaMalloc` を試す。allocation が失敗したとき、本変数が未設定などの gate を通れば mapped pinned host memory を確保して tensor をコピーし、成功時は「short of GPU memory」ログを出す。本変数が設定されている場合はこの fallback block に入らず、失敗 status のまま scratch allocation とコピー段を経て upload error を返す。通常の single GPU 呼び出し側はエラーを stderr に出し `return 1` する。layer split の load 失敗も CUDA stage と head error を stderr に出し `return 1` する。参照: `engine/src/core/native_head.cpp:125-130,218-252`、`engine/src/program/generate.cpp:7775-7782,8388-8400`。

serve の `--prefill-head-alias` 経路では、head を unload した後の restore で `NativeHead::load` を再度呼ぶため、その呼び出しごとにこの値を読み直す。参照: `engine/src/program/generate.cpp:19164-19180`。

初回 upload が成功して VRAM 上に head がある場合も、cache 計画で slot がなくなるなどの条件を満たせば後段の host 退避対象になる。`NativeHead::to_host` は split head、未ロード・すでに host 上の head、および packed Q6_K/Q8_0 head を拒否する。それ以外は pinned host buffer を作り、VRAM から copy してから VRAM allocation を解放する。失敗時には理由文字列があればそれをログに出し、型や build により移動不可なら `type or build not movable` を表示する。本変数を設定すると、この `to_host` 呼び出し自体が抑止される。参照: `engine/src/core/native_head.cpp:297-317`、`engine/src/program/generate.cpp:9350-9373,9903-9918`。

単一 GPU 経路では退避を止めても、その場で必ず終了するとは限らない。head を VRAM に残したまま後続の cache 計算へ進み、slot が不足する場合は `no VRAM is left for the expert cache` の案内を stderr に出す。layer split 経路では room 計算を続け、各 stage の free memory と expert room を出力する。各経路のその後の開始可否は残りの VRAM と cache 配置処理に依存する。参照: `engine/src/program/generate.cpp:9368-9373,9398-9418,9910-9924`。

## ログと測定値

退避が実行される場合のログは、upload 時に `strata generate: short of GPU memory: the output head (... MiB) stays in pinned host memory and is read over PCIe for every logits row: decode is slower`、single GPU cache 計画時に `strata generate: short of GPU memory: the cache had no room, so the output head (... MiB) moves to pinned host memory and is read over PCIe for every logits row: decode is slower; the cache is now ... slots`、layer split 時に `strata generate: short of GPU memory: CUDA%d: the cache would have no room, so the output head (... MiB) moves to pinned host memory and is read over PCIe for every logits row: decode is slower; the room for experts is now ... GiB` を stderr に出す。本変数が退避を抑止した際の専用警告はなく、通常の upload error または cache 不足メッセージへ進む。参照: `engine/src/core/native_head.cpp:234-235,251`、`engine/src/program/generate.cpp:9368-9373,9411-9418,9910-9918`。

性能値は記載しない。現行ソースのコメントには特定条件下の速度例があるが、この環境変数の文書として条件付き測定値を裏付ける設計資料の記述は確認できなかった。

## 根拠

- `engine/src/core/native_head.cpp:130-135,218-252` — `STRATA_HEAD_HOST` の明示要求、GPU allocation 失敗時の fallback gate、host allocation と upload error。
- `engine/src/core/native_head.cpp:297-317` — host へ移せる head の条件と移動処理。
- `engine/src/program/generate.cpp:326-339`、`engine/include/strata/core/spill_gate.hpp:8-14` — discrete GPU の gate と Metal/integrated GPU の除外。
- `engine/src/program/generate.cpp:8382-8400,9346-9373,9398-9418` — 単一 GPU の load 順序、cache 不足時の head 退避と継続処理。
- `engine/src/program/generate.cpp:9903-9924` — layer split の最終 stage に対する退避と room 計算。
- `engine/src/kernels/cuda/native_mmvq.cu:3145-3151` — `STRATA_Q6_PACKED` の有効判定（完全に `"1"` の場合）。
