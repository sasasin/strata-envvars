# `--peer-slots`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ engine の引数 parser） |
| オプション | `--peer-slots` |
| 別名 | なし |
| 値 | 整数 `N`。peer 側 expert cache の最大 slot 数として使う |

## 役割

`--peer-device` で有効にする第2 GPU の expert tier に入れる expert 数の上限です。指定数を確保する保証ではなく、peer GPU の空き VRAM と primary 側にない expert の数の範囲で、profile の順位順に確保します（`src/program/generate.cpp:570-575`、`include/strata/core/peer_experts.hpp:42-46`、`src/core/peer_experts.cpp:191-212`）。

## 使い方

```sh
strata --pack ./pack --tokens 1,2 --expert-profile ./profile.bin \
  --expert-cache 1024 --peer-device 1 --peer-slots 256
```

`--peer-slots` は単独では peer GPU を有効にしません。`--peer-device N` と expert profile、正の `--expert-cache` を指定した実行で peer tier の初期充填に使われます（`src/program/generate.cpp:6750-6766`）。

## 値と既定値

- parser は `std::atoll` で値を読み、既定値は `0` です。help 表示も既定を「what fits」としています（`src/program/generate.cpp:570-575, 1012-1014, 2743-2747`）。
- `N > 0` のとき、peer に入れる expert 数を最大 `N` に制限します。空き VRAM の予算に達した場合や候補が尽きた場合は、`N` より少なくなります（`src/core/peer_experts.cpp:191-208`）。
- `N = 0` は上限なしです。実装は `max_slots > 0` のときだけ上限を検査するため、負数も上限なしとして扱います。負数を拒む validation はありません（`src/program/generate.cpp:2745`、`src/core/peer_experts.cpp:203-205`）。
- 同じオプションを複数回指定した場合は parser が順に代入するため、最後の値が残ります（`src/program/generate.cpp:2416-2421, 2745`）。数値として変換できない文字列は `atoll` により `0` になります。値の形式・範囲を別途検査する分岐は確認できません（`src/program/generate.cpp:2745`）。
- 値を省略すると `--peer-slots needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

peer tier の初期化時、primary がすでに保持している expert を除き、ranked profile の順で各 expert の blob サイズを空き VRAM 予算へ加算します。予算を超える次候補があればそこで打ち切り、さらに `N > 0` なら選択済み件数が `N` に達した時点でも打ち切ります。したがってこの値は初期 resident 数の上限であり、後続の adaptive swap 数を決めるものではありません（`src/core/peer_experts.cpp:191-208`）。

peer device は `--peer-device` が指定された場合に限り初期化されます。その際、`--expert-profile` と有効な expert cache が必要です。また `--layer-split`、`--expert-cache-device1..3` とは併用できません。これらの条件は `--peer-slots` 自体の validation ではなく peer GPU を構成する条件です（`src/program/generate.cpp:3369-3375, 6750-6766`）。

## 適用条件と副作用

- CUDA 実装では peer GPU の scratch・cache 領域を確保し、選ばれた expert blob を読み込んで初期充填します。`--peer-slots` はその cache 領域に入れる expert 数を抑えますが、別の peer runtime 用領域の確保より前に適用される値ではありません（`src/core/peer_experts.cpp:165-185, 191-240`）。
- この tier は CUDA device 1 以上向けです。device が可視でない場合や、空き領域・候補がなく一件も選べない場合は初期化に失敗します（`src/core/peer_experts.cpp:127-134, 191-212`）。
- SYCL build でも parser は同じ値を受け取りますが、peer tier は未移植のため、`--peer-device` を有効にすると `--peer-device: the second-GPU expert tier is not ported to SYCL yet` で失敗します。従って SYCL では `--peer-slots` は peer cache を構成しません（`sycl/src/program/generate.cpp:2020-2024, 5260-5272`、`sycl/src/core/peer_experts.cpp:19-23`）。
- `--peer-device` を指定しない場合、保存された `peer_slots` は peer 初期化に渡されず、実行上の効果はありません（`src/program/generate.cpp:575, 6750-6759`）。

## 出力とエラー

peer GPU の初期化成功後は stderr に GPU 番号、resident expert 数、使用 GiB、充填時間などを出力します。失敗時はエラーを `strata generate:` に続けて stderr に出し、終了コード `1` で終了します。peer cache に一件も選べない場合のエラーは `peer experts: no room or no expert left for the peer` です（`src/program/generate.cpp:6758-6766`、`src/core/peer_experts.cpp:209-212`）。

## 根拠

- parser、既定値、help: `src/program/generate.cpp:570-575, 1009-1014, 2743-2747`
- 値省略時の parser 動作: `src/program/generate.cpp:2416-2421`
- peer 初期化条件と結果表示: `src/program/generate.cpp:3369-3375, 6750-6766`
- slot 上限、VRAM 予算、候補選択、初期充填: `include/strata/core/peer_experts.hpp:42-46`、`src/core/peer_experts.cpp:191-240`
- SYCL build の制約: `sycl/src/core/peer_experts.cpp:19-23`、`sycl/src/program/generate.cpp:5260-5272`
- 関連資料（ソースの補助資料）: `docs/SECOND_GPU.md:140-180`

## 調査範囲

調査時点の checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、branch `main` で、`git status --short --branch` は `## main...origin/main` でした。CUDA と SYCL の parser・peer 初期化を確認しました。実行バイナリ、各 GPU 構成、実際の CLI `--help` 出力は確認していません。挙動の記述は上記ソースに基づきます。
