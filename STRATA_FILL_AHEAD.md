# `STRATA_FILL_AHEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

GPU expert cache を起動時に profile から埋める際、mapped file tier のどの程度先の expert blob まで OS に読み込みを事前依頼するかを指定します。値は profile の先読み対象数（pair 数）で、キャッシュ容量や fill する pair 自体は変えません。CUDA/HIP 側と SYCL 側に同じ設定処理があります。

## 値と判定

実装は `std::atoi` で整数変換し、その結果を `std::max(0, ...)` で 0 以上にします。文字列全体の検証はしません。

| 値 | 結果 |
|---|---|
| 未設定 | 256 |
| 空文字 | 0 |
| `0`、負数 | 0 |
| 正の整数 | その整数 |
| 数字で始まらない文字列 | `atoi` の結果 0 |
| 数字の後ろに文字が続く値 | 数字として読めた先頭部分（例: `12xyz` は 12） |

`atoi` の通常の規則により、先頭の空白と符号は整数変換時に扱われます。値の読み取りは profile fill の開始時に行われます。設定値が対象外経路で参照されない場合、環境値は読まれず、この変数由来のログも出ません。

## 有効になる条件

次をすべて満たす mapped file tier の profile fill が対象です。

- profile が空でなく、expert source が存在する。
- per-layer admission ではない。
- source が通常の file source (`src`) である。resident arena source は対象外。
- file source が unbuffered ではない。
- `FileExpertSource::advise_pairs()` が mapped data を扱え、`STRATA_READ_AHEAD` により read-ahead が無効化されていない。

SYCL では加えて GGUF からの pipelined fill (`--stream-experts` の通常経路) 中は対象外です。`STRATA_FILL_SERIAL` が設定されて pipelined fill を使わない場合は、他の条件を満たせば対象になります。CUDA/HIP の fill にはこの `piped` 判定はありません。

read-ahead の platform 実装は Windows では常に無効です。Linux では `STRATA_READ_AHEAD` が未設定なら有効で、設定時は `atoi(value) != 0` の場合だけ有効です。したがって `STRATA_READ_AHEAD=0`、または非数値の値では `advise_pairs()` が失敗を返し、この変数の有効数は 0 に変更されます。

## 実行時の詳細

有効経路では、まず profile の先頭から `min(STRATA_FILL_AHEAD, want)` pair を `advise_pairs()` に渡します。最初の依頼が成功した場合、fill loop の各 pair `i` について、`i + fill_ahead < want` の間、`i + fill_ahead` 番目の pair を1件ずつ追加で依頼します。これにより、現在の pair を GPU cache slot に読み込んでいる間に、先の mapped file pages も読み込み対象として OS に通知します。`want` は per-layer admission であれば profile 全体、そうでなければ profile 数と cache slot 数の小さい方です。

`advise_pairs()` は Windows、unmapped source、unbuffered/direct source、または read-ahead 無効時に `false` を返します。呼び出し元は最初の依頼が `false` なら `fill_ahead` を 0 にし、その後の逐次依頼も行いません。pair ごとの後続依頼の戻り値は無視されます。source 側は mapped blob の範囲（分割 role の場合は各 role の範囲）に対して `advise_willneed()` を呼び、Linux 実装は `madvise(MADV_WILLNEED)` を 128 KiB 単位で依頼します。これは読み込み完了を待つ処理ではありません。

対象経路では stderr に `strata generate: the profile fill asks for %lld pairs ahead (STRATA_FILL_AHEAD)` が出ます。ここで表示される数は初回依頼が失敗した場合は 0 です。profile fill 自体は起動時に一度実行されるため、実行中に環境変数を変更してもその fill には反映されません。

## 根拠

- `src/program/generate.cpp:4621-4699,5141-5180`: file source の選択、profile fill、条件、既定値・変換・逐次先読み、ログ。
- `sycl/src/program/generate.cpp:4150-4200,4593-4745`: SYCL の source 選択、pipelined 経路の判定、同じ変換と先読み処理。
- `src/core/expert_source.cpp:1502-1517`、`sycl/src/core/expert_source.cpp:951-966`: `advise_pairs()` の適用条件と mapped blob / role の指定。
- `src/platform/memory.cpp:117-119,150-170`、`include/strata/platform/memory.hpp:56-62`: Windows での無効化、Linux の `STRATA_READ_AHEAD` 判定、128 KiB 単位の `MADV_WILLNEED`。
- `docs/DETAILS.md:282-286`: Linux read-ahead の説明、`STRATA_FILL_AHEAD=N` の既定値 256。
