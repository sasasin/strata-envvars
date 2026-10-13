# `STRATA_PREFILL_AUTO_MAX`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--prefill auto` が自動選択する prompt chunk の上限を、既定の 8192 token から 16384 または 32768 token に引き上げます。上限を指定する変数であり、実際にそのサイズが選ばれるかは expert cache から prompt buffer を借りられるか、context 長などで決まります。CUDA/HIP 系と SYCL の `generate` 実装にあります。

## 値と判定

この変数は `--prefill` の引数を解析する箇所で `getenv()` されます。`--prefill` がなければ読み取られず、数値 chunk を指定した場合も効果はありません。値は `atoll()` で変換し、しきい値で次の3段階に丸めます。文字列全体の妥当性検査やエラー表示はありません。

| `--prefill` | 環境変数 | `prefill_auto_max` |
|---|---|---:|
| `auto` | unset | 8192 |
| `auto` | `atoll()` の結果が 16384 未満 | 8192 |
| `auto` | `atoll()` の結果が 16384 以上 32768 未満 | 16384 |
| `auto` | `atoll()` の結果が 32768 以上 | 32768 |
| `auto:N` | 任意 | `N` を `atoll()` した値を同じしきい値で丸めた値。環境変数より CLI が優先 |
| 数値など `auto` 以外 | 任意 | 環境変数は不使用 |

したがって `16384junk` は 16384、`32768` 以上の数値に続く文字は無視されます。空文字、数値で始まらない文字列、0、負数は変換結果がしきい値未満となり 8192 です。値そのものの数値範囲検査はありません。

## 有効になる条件

- 自動 chunk の上限になるのは `--prefill auto` または `--prefill auto:N` を指定し、後段でも `prefill_auto` が有効な場合です。
- `--no-prefill-borrow` が指定された場合、または expert profile が空の場合、自動借用を無効にして chunk を 2048 に戻します。SYCL にも、この後段の同じ無効化があります。
- 自動選択は設定上限を超えず、context 長も超えない範囲で、借用できる cache slot / buffer と ring の予算を見て chunk を決めます。したがって上限を 32768 にしても、32768 が必ず使われるわけではありません。
- CUDA/HIP 実装では Windows HIP の bare `--prefill auto` に 6144 の cap がありますが、`STRATA_PREFILL_AUTO_MAX` が設定されていれば bare auto 扱いではなくなり、この特別 cap は付きません。値が空や不正でも「設定あり」と判定されます。
- Linux HIP gfx12 の bare `--prefill auto` は、変数が未設定なら別の gfx12 条件により 16384 へ上げられる場合があります。変数が設定されているとこの bare-auto 分岐は使われず、値に応じた 8192/16384/32768 の上限になります。`STRATA_GFX12_CHUNK=0` または `STRATA_GFX12_DEFAULTS=0` は、変数未設定の bare-auto gfx12 引き上げを止めます。

## 実行時の詳細

値は `--prefill` の引数解析時に読み込まれ、`prefill_auto_max` などの option fields に保存されます。後の auto planning はその保存値を上限として、cache lending に適合する chunk を選びます。プロセス実行中に環境を書き換えて再読込する処理はありません。

CUDA/HIP と SYCL の両方で `auto:N` は環境変数に優先します。CUDA/HIP の Windows HIP cap / gfx12 の条件は前述のとおり bare auto の判定にも使われます。設定値による専用ログや警告はありません。

## 根拠

- `src/program/generate.cpp:1946-1971`: `--prefill` の解析、`atoll()`、上限丸め、Windows HIP bare-auto 判定と cap。
- `src/program/generate.cpp:2160-2175`: Linux HIP gfx12 の bare auto 上限と、環境変数設定時はこの調整をしない条件。
- `src/program/generate.cpp:2426-2429`: borrow 不可または expert profile 不在時に auto を無効化し、chunk を 2048 にする処理。
- `src/program/generate.cpp:6296-6301,6320-6328`: 自動計画上限の context clamp と候補 chunk の上限判定。
- `sycl/src/program/generate.cpp:1790-1798,2221-2224,5953-5985`: SYCL 側の同じ値変換と、auto の無効化・上限を使った候補選択。
- `include/strata/platform/host_limits.hpp:19-30`: Windows HIP bare auto の cap と、ユーザー指定 chunk の警告条件。
- `docs/DETAILS.md:1947`: gfx12 の説明。bare auto だけが対象で、明示 chunk / `auto:N` / `STRATA_PREFILL_AUTO_MAX` はこの調整の対象外と記載されています。
