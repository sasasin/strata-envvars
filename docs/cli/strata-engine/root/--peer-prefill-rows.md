# `--peer-prefill-rows`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ engine の root parser。prompt 処理への効果は `--serve` 時） |
| オプション | `--peer-prefill-rows` |
| 別名 | なし |
| 値 | 整数 `N`。peer GPU が各 prompt chunk の各層で処理する MoE row 数の上限として扱われる（ただし compact 経路では上限が全 row 数に置き換わる） |

## 役割

`--peer-device` で構成した peer GPU に prompt prefill の expert row 処理を分担させる際の row 上限を指定します。peer GPU による expert cache と decode の設定そのものは `--peer-device` 側で行います。このオプションが prompt path の初期化に使われるのは `--serve` の経路です。通常の生成経路で peer cache が開かれても、この値による prefill path の設定は行われません（`src/program/generate.cpp:6750-6767, 8884-8890`）。

## 使い方

```sh
strata --serve --pack MODEL --peer-device 1 --peer-prefill-rows 256
```

peer GPU を使いながら prompt path の peer 分担を止める例:

```sh
strata --serve --pack MODEL --peer-device 1 --peer-prefill-rows 0
```

`--peer-device` を有効にする場合、engine は `--expert-profile` と expert cache も必要とします（`src/program/generate.cpp:6751-6759`）。

## 値と既定値

- 既定値は `-1` です。`--prefill` で決まる chunk サイズを `T`、モデルの top-k を `K` とすると、`-1` を含む負数は `T × K / 2` に置き換えられます（`src/program/generate.cpp:577-579, 8884-8886`）。
- `0` の場合、peer が有効でも `Prefill::set_peer` を呼ばず、prompt path は primary GPU のままです。peer expert cache 自体を無効にはしません（`src/program/generate.cpp:8884-8889`）。
- 正数は指定値が上限になります。非 compact 経路では `1` から `T × K` の範囲に丸められます。値が `T × K` より大きい場合は `T × K` までです（`src/prefill/prefill.cpp:2054-2059`、SYCL: `sycl/src/prefill/prefill.cpp:1961-1965`）。
- parser は値を `std::atoll` で読み、オプション固有の範囲検証や数値形式検証をしていません。値を省略すると `--peer-prefill-rows needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2416-2421, 2747`）。

## 実行時の動作

`--serve` の prompt path を初期化した後、peer が有効かつ値が 0 でなければ、正数はそのまま、0 未満は `prefill_chunk × K / 2` に変換して `Prefill::set_peer` に渡します。prefill 処理では各層の expert rows を peer に割り当てる際に累積 row 数が `cap_rows` を超える expert を peer 対象から外し、残りを primary 側で処理します（`src/program/generate.cpp:8884-8889`、`src/prefill/prefill.cpp:3888-3904`）。

ただし既定の compact 経路ではこの数値上限は適用されません。CUDA 実装は `STRATA_PF_PEER_COMPACT` が未指定または非ゼロなら compact を使い、P2P がない場合も compact に固定します。SYCL 実装も同環境変数の未指定または非ゼロで compact を使います。compact の初期化は `cap_rows` を `T_max × K`（chunk 全体の row 数）へ置き換えるため、通常の既定設定では正数を指定しても row 上限は縮小しません。上限を使うには P2P 接続に加え `STRATA_PF_PEER_COMPACT=0` が必要です（CUDA: `src/prefill/prefill.cpp:2092-2100`、SYCL: `sycl/src/prefill/prefill.cpp:2017-2025`）。

## 適用条件と副作用

- peer が有効でなければ、この値は prompt path に作用しません。`--peer-device` は `--layer-split` および `--expert-cache-device1..3` と併用できず、`--expert-profile` と expert cache が必要です（`src/program/generate.cpp:3371-3375, 6751-6759`）。
- peer prefill には MMQ prompt path が必要です。CUDA では P2P がなくても host route を許可する環境設定の場合は続行できますが、SYCL では P2P がないと設定失敗になります（CUDA: `src/prefill/prefill.cpp:2036-2043`、SYCL: `sycl/src/prefill/prefill.cpp:1955-1965`）。
- CUDA で NVFP4 expert を含む native pack は未対応です。Hadamard-folded (APR) pack では CUDA 実装が警告を出して peer prefill を使わず、prompt は primary に残します（`src/prefill/prefill.cpp:2044-2053`）。
- peer prefill 用の GPU buffer や、host route で必要な pinned host memory を確保します。必要な peer buffer が確保できない場合、設定は失敗します（`src/prefill/prefill.cpp:2086-2095, 2191-2201`）。

## 出力とエラー

- peer prefill の設定成功時は stderr に、peer GPU が各 prompt chunk の各層で処理する row 上限と残り VRAM を表示します（`src/prefill/prefill.cpp:2201-2209`）。
- `set_peer` の失敗時は `strata serve: <理由> - the prompt path stays on the primary GPU` を stderr に出し、エラーをクリアして処理を続けます。したがって、この失敗だけでは serve 全体を終了しません（`src/program/generate.cpp:8886-8889`）。GPU buffer 不足時の理由には `--peer-reserve-mib` を増やすか本オプションを下げるよう案内する文言があります（`src/prefill/prefill.cpp:2201`）。

## 根拠

- `src/program/generate.cpp:577-579, 1015-1016` — 既定値と engine help の説明。
- `src/program/generate.cpp:2416-2421, 2747` — 値の取得、欠落時エラー、整数変換。
- `src/program/generate.cpp:6750-6767, 8884-8889` — peer の前提条件と serve prompt path への適用。
- `src/prefill/prefill.cpp:2036-2059, 2092-2100, 2191-2215, 3888-3904` — CUDA の適用条件、上限、compact 経路、確保失敗と row 割当。
- `sycl/src/program/generate.cpp:555-557, 916-917, 2024, 7119-7124`、`sycl/src/prefill/prefill.cpp:1955-1965, 2017-2025, 2092-2098` — SYCL の parser と peer prefill の条件・compact 経路。

調査範囲は checkout 内の CUDA と SYCL の parser・実装です。CLI の実行、build、GPU 実行、テストは行っていません。
