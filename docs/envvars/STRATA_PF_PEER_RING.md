# `STRATA_PF_PEER_RING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 系と SYCL の prompt peer streaming が使う、peer GPU 側の expert staging ring の slot 数を指定する。peer 用 ring の既定値は 48 slots で、設定されていればこの変数を `atoi` した値で置き換える。各 slot に expert blob の staging buffer と copy/use event を用意し、stream 中の expert を順次再利用する。通常の decode 用 peer cache 全体の slot 数や、primary GPU 側の ring は変更しない。`Prefill::set_peer` 内で peer prompt 用の compact buffer を構成するときに読む（CUDA/HIP 系: `engine/src/prefill/prefill.cpp:3333-3343,3433-3455`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2243-2253,2322-2345`）。

## 値と判定

両実装とも `std::getenv` が null でなければ `std::atoi` の結果をそのまま `RP` に入れる。数値の妥当性検査、範囲制限、無効値の fallback はない。`atoi` は文字列全体の厳密な数値 parse ではないため、数値の前に空白や符号を許し、数値部分の後ろは無視する。数値に変換できない先頭なら 0 になる。読み取り行は CUDA/HIP 系 `engine/src/prefill/prefill.cpp:3444-3447`、SYCL `engine/sycl/src/prefill/prefill.cpp:2324-2327`。

| backend / 条件 | unset | 設定時に使われる値 | 境界・無効値の扱い |
|---|---:|---|---|
| CUDA/HIP 系: peer streaming の条件成立時 | 48 | `atoi` の整数値。例: `12` → 12、`2x` → 2、`  +3tail` → 3 | 空文字、`x`、`0` は 0。負数もそのまま保持。clamp や拒否なし |
| SYCL: peer streaming の条件成立時 | 48 | 同上 | 同上 |
| peer streaming の条件不成立時 | peer ring を構築せず、この変数を読まない | 読まない | 値は当該 `set_peer` 呼び出しでは影響しない |

0 は無効値として扱われず、0 slots の各 vector が作られる。peer streaming が実際に peer-ring entry を処理するときは `P.p_issued % (size_t) P.RP` 等で slot を選ぶため、`RP=0` のままその経路に入るとゼロ除算を含む不正な実行になる（CUDA/HIP 系 `engine/src/prefill/prefill.cpp:4644-4650,6761-6766`、SYCL `engine/sycl/src/prefill/prefill.cpp:3094-3101,4390-4396`）。負数も拒否されず vector のサイズへ `size_t` 変換されて使われるため、巨大サイズ確保に進み得る。安全な下限・上限はコードに定義されていない。

## 有効になる条件

- peer GPU が有効で、CLI の `--peer-prefill-rows` が 0 でない場合に `Prefill::set_peer` が呼ばれる。CUDA/HIP 系と SYCL の呼び出し元は `engine/src/program/generate.cpp:13146-13150` と `engine/sycl/src/program/generate.cpp:7608-7612`。
- peer GPUs に P2P access がなく、`STRATA_PF_PEER_HOST=0` の場合は `set_peer` が早期に false を返すため、この変数の読み取りまで到達しない（CUDA/HIP 系 `engine/src/prefill/prefill.cpp:3335-3340`）。P2P の有無そのものは peer ring slot 数を変えず、P2P がない場合は host route が有効なら CUDA/HIP 系で compact path が強制される。
- `set_peer` が成功し、compact peer prompt path が使われること。CUDA/HIP 系では `STRATA_PF_PEER_COMPACT=0` でも P2P が使えない場合 compact が強制される（`engine/src/prefill/prefill.cpp:3412-3415`）。SYCL では unset または `atoi != 0` のとき compact（`engine/sycl/src/prefill/prefill.cpp:2307-2310`）。非 compact なら `STRATA_PF_PEER_RING` は参照されない。
- `STRATA_PF_PEER_STREAM` が正数で、全 peer layer が streaming 対応し、chunk の `T_max` が `stream_all_min()` 以上であること。CUDA/HIP 系は `all_peer_layers`、SYCL は `!mp.fallback` も条件にする。`STRATA_PF_PEER_STREAM` は設定時 `atof` で変換され、空文字や数値で始まらない値は 0 となる。CUDA/HIP 系の unset 既定 share は通常 0.35、`STRATA_PF_OWN_ONLY` build かつ peer int8 layer がある場合は 0.0。SYCL は unset 時 0.35。条件を満たさない場合は `ps_frac=0` に戻され、ring は使われない（CUDA/HIP 系 `engine/src/prefill/prefill.cpp:3343-3354,3437-3459`、SYCL `engine/sycl/src/prefill/prefill.cpp:2322-2348`）。
- CUDA/HIP 系では `STRATA_PF_OWN_ONLY` build かつ peer int8 layer があると、`STRATA_PF_PEER_STREAM` 未設定時の既定値は 0.0 になる。明示的な正数 share なら上記条件に進む（`engine/src/prefill/prefill.cpp:3419-3423,3437-3445`）。SYCL 実装は未設定時 0.35 を直接使う（`engine/sycl/src/prefill/prefill.cpp:2322-2326`）。
- `--peer-prefill-rows` は peer prompt path を作るかどうかの CLI gate で、ring slot 数を上書きしない。GPU staging buffer の確保エラーなど `set_peer` が false を返す場合、呼び出し元は `strata serve: <理由> - the prompt path stays on the primary GPU` を出して primary GPU に戻す。大きな値で標準 vector の確保自体が例外になるケースに対する `STRATA_PF_PEER_RING` 固有の回復処理はないため、成功する ring サイズは保証されない（CUDA/HIP 系 `engine/src/prefill/prefill.cpp:3534-3537`、SYCL `engine/sycl/src/prefill/prefill.cpp:2374-2385`、呼び出し元は上記 generate.cpp の行）。

## 実行時の詳細

値は `Prefill::set_peer` が peer prompt path を構成するたびに読み取られ、static cache はない。CUDA/HIP 系では `ps_frac > 0`、全 peer layer 対応、chunk 閾値の条件が成立した後に `RP=48` を設定してから環境変数で上書きする。SYCL も同じ順で `RP=48` を設定するが、対応条件は `!mp.fallback` を使う。両方とも `RP` 個の staging pointer、copied/used event、live flag を用意し、各 slot に `MAXBLOB()` bytes の staging storage を割り当てる（CUDA/HIP 系 `engine/src/prefill/prefill.cpp:3444-3455`、SYCL `engine/sycl/src/prefill/prefill.cpp:2324-2345`）。

prompt stream の計画では pinned expert のうち `ps_frac` に従って選んだものを peer ring queue に入れる。初期分を `RP` 件まで発行し、slot 番号を entry index modulo `RP` で巡回させ、copy 完了と slot 使用完了を event で同期して再利用する（CUDA/HIP 系 `engine/src/prefill/prefill.cpp:4644-4655,4700-4705,4947-4952`、SYCL `engine/sycl/src/prefill/prefill.cpp:3094-3116,3172-3178,3316-3329`）。値自体は prompt path の構築時に読み取るので、構築後に環境を書き換えても現在の `PeerPrefill` の `RP` や確保済み vector/buffer は変わらない。次の再構築時に再読込される。

## ログと測定値

構築成功時、`strata prefill: peer GPU ...` のログに peer ring の slot 数が `... through a <N>-slot ring` として含まれるのは `ps_frac > 0` かつ compact path の場合。`STRATA_PF_PEER_RING` 固有の値検証警告やエラー文はない（CUDA/HIP 系 `engine/src/prefill/prefill.cpp:3537-3545`、SYCL `engine/sycl/src/prefill/prefill.cpp:2380-2385`）。ソースの stream-share コメントには別変数 `STRATA_PF_PEER_STREAM` の測定値があるが、この ring slot 数の性能測定条件・比較値は記載されていないため記載しない。

## 根拠

- 全直接参照と ring 設定: `engine/src/prefill/prefill.cpp:3444-3455`、`engine/sycl/src/prefill/prefill.cpp:2322-2345`。
- peer prompt path の起動条件: `engine/src/program/generate.cpp:13146-13150`、`engine/sycl/src/program/generate.cpp:7608-7612`。
- ring entry の選択・同期・再利用: `engine/src/prefill/prefill.cpp:4644-4655,6761-6786`、`engine/sycl/src/prefill/prefill.cpp:3094-3116,4379-4410`。
- 成功ログと確保失敗: `engine/src/prefill/prefill.cpp:3534-3545`、`engine/sycl/src/prefill/prefill.cpp:2368-2385`。
