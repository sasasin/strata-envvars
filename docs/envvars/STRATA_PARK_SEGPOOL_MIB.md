# `STRATA_PARK_SEGPOOL_MIB`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`--serve` の会話 cache が保持する parked conversation の K/V 用ホストメモリについて、会話バッファの segment が通常の `::operator new` に加えて利用できる process-wide arena の希望サイズを MiB で指定する。arena は idle のページをバックグラウンドで先に resident にし、割当済み範囲を解放したときもページを resident のまま pool に戻す。parked image の K/V 内容や選択される会話は変えず、バッファの割当元だけを変える設計である。pool が無効・不足・利用不能なら通常ヒープ割当に戻る。[`generate.cpp:514-520`](../../../../Niko1221/Strata/src/program/generate.cpp)、[`conversation_buffer.hpp:18-30`](../../../../Niko1221/Strata/include/strata/core/conversation_buffer.hpp)

## 値と判定

エンジンは `std::getenv` で値を取り、関数内 `static const long long` を初回呼び出しで一度だけ初期化する。未設定は `-1`（自動値を使う印）、設定値は `std::atoll` で変換し、変換結果が正ならその値、0 以下なら 0 にする。`atoll` に渡す文字列全体の厳密な数値検証はなく、先頭の空白や符号は変換関数の規則に従い、数値の後ろの非数値部分は変換を止める。したがって空文字・数字で始まらない文字列・`0`・負値は 0 になる一方、`128junk` は 128 として扱われる。値の parse 自体には MiB 上限がない。[`generate.cpp:521-529`](../../../../Niko1221/Strata/src/program/generate.cpp)

| 条件 | unset | 有効になる値（例） | 無効・無効化される値（例） |
| --- | --- | --- | --- |
| 全 OS 共通の値判定 | `-1` を返し、後述の自動値を使用 | `128`、`128junk` は正数として指定 | 空文字、`x`、`0`、`-1` は 0（pool を要求しない） |
| pool サイズの適用 | cache 予算から既定値を算出 | 正の指定値。ただし cache の 1/4 以下に制限 | 適用後 0、または 2 MiB 未満では arena が作られない／有効にならない |

`--conversation-cache-mib` が会話 cache の予算を決め、環境変数の正数はその予算の最大 1/4 に切り詰められる。unset 時の自動値は `min(2048 MiB, cache_mib / 4)` を 64 MiB 単位に切り下げ、128 MiB 未満なら 0。明示値はこの自動値を置き換えるが、最終的にも cache の 1/4 上限を受ける。予約サイズは 2 MiB 単位に切り下げられるため、2 MiB 未満なら pool は inactive となる。サイズ算出と cache 予算の関係は [`generate.cpp:13011-13016`](../../../../Niko1221/Strata/src/program/generate.cpp)、[`park_pool_policy.hpp:18-32`](../../../../Niko1221/Strata/include/strata/core/park_pool_policy.hpp) にある。

## 有効になる条件

- `--serve` の処理で会話 cache が有効であること。cache は `--prompt-cache` が正で、cache 予算と slot 数が 0 でない場合に有効になる。`--conversation-cache-mib 0`、`--conversation-cache-slots 0`、または prompt cache 無効では pool を使わない。[`generate.cpp:12934-12940,12964-12970`](../../../../Niko1221/Strata/src/program/generate.cpp)、[`conversation_cache.hpp:266-268`](../../../../Niko1221/Strata/include/strata/core/conversation_cache.hpp)
- parse 後の要求サイズが正であること。0 以下では明示的に pool を off にする。明示値を自動値に足したり、CLI 値より優先して cache 予算を拡大したりはしない。[`generate.cpp:523-527,13011-13016`](../../../../Niko1221/Strata/src/program/generate.cpp)
- Linux であること。Linux 実装は `mmap` で予約し、`madvise(MADV_POPULATE_WRITE)` を使い、`EINVAL` の場合だけページごとの atomic write にフォールバックする。Windows/macOS を含む非 Linux の `NoSegmentPoolOs::reserve` は常に null を返し、値が正でも pool は inert である。[`conversation_segment_pool.hpp:28-31,49-93`](../../../../Niko1221/Strata/include/strata/core/conversation_segment_pool.hpp)
- 2 MiB 以上の予約可能な領域があり、process-wide pool の初回 install に成功すること。予約失敗や install 失敗時は pool を使わず、segment の割当は `::operator new` にフォールバックする。[`conversation_segment_pool.hpp:105-123,134-164,307-313`](../../../../Niko1221/Strata/include/strata/core/conversation_segment_pool.hpp)、[`conversation_buffer.hpp:22-30`](../../../../Niko1221/Strata/include/strata/core/conversation_buffer.hpp)
- 実際の個別割当が pool に入るには segment が 512 KiB 以上で、pool に適合する空き範囲があること。満たさない割当は通常ヒープを使う。[`conversation_segment_pool.hpp:105-112,134-148`](../../../../Niko1221/Strata/include/strata/core/conversation_segment_pool.hpp)
- background のページ補充はエンジンが idle で、cache 予算内かつ `--conversation-cache-min-free-mib` の RAM floor と追加 1 GiB を保てる場合だけ進む。要求時に pool の補充を待たず、pool が応じられなければヒープへ fallback する。[`generate.cpp:13003-13009,13019-13031`](../../../../Niko1221/Strata/src/program/generate.cpp)、[`park_pool_policy.hpp:36-40`](../../../../Niko1221/Strata/include/strata/core/park_pool_policy.hpp)

## 実行時の詳細

値は `park_segpool_env_mib()` の初回呼び出し時に読み、以後は関数内 static に保存する。serve 中に環境変数を変更しても再評価されない。serve の cache 予算確定後、pool を構築・install し、会話バッファは install 済み pool に空きがあればそこから segment を取得する。arena は 256 KiB granule で管理し、Linux の予約長は 2 MiB 単位。pool を使えない場合は通常の `::operator new` / `::operator delete` に戻る。[`generate.cpp:521-529,12936-12970,13011-13041`](../../../../Niko1221/Strata/src/program/generate.cpp)、[`conversation_segment_pool.hpp:105-123,134-177`](../../../../Niko1221/Strata/include/strata/core/conversation_segment_pool.hpp)、[`conversation_buffer.hpp:22-30`](../../../../Niko1221/Strata/include/strata/core/conversation_buffer.hpp)

補充 thread は `segpool_kick()` で初回および後続のタイミングに起動要求され、最大 32 MiB の step で idle の cold granule を resident 化する。park 前の物理 RAM admission が通らず pool に idle bytes があれば、cache の画像や会話を退避する前に pool の idle ページを縮小して再判定する。pool の idle bytes は会話 cache の予算にも算入され、画像の予算超過退避より先に返却される。[`generate.cpp:13003-13009,13019-13031,13315-13324`](../../../../Niko1221/Strata/src/program/generate.cpp)、[`conversation_cache.hpp:275-282,406-420`](../../../../Niko1221/Strata/include/strata/core/conversation_cache.hpp)、[`conversation_segment_pool.hpp:180-217,257-293`](../../../../Niko1221/Strata/include/strata/core/conversation_segment_pool.hpp)

## ログと測定値

`STRATA_PARK_TRACE` が設定されている場合（値の内容ではなく `getenv != nullptr` の有無）、成功時に `strata parktrace: segpool %zu MiB reserved (%s %zu MiB, cache %lld MiB)`、予約または install 失敗時に `strata parktrace: segpool not reserved (%zu MiB wanted)` を stderr に出す。続く状態行の書式は `strata parktrace: park pools: segment pool %zu MiB, checkpoint pool %s (ready %zu, cap %zu, %zu MiB each), cache %zu MiB, stages %zu`。`STRATA_PARK_TRACE` 未設定時はこれらの pool 状態ログは出ない。pool 予約失敗自体で Strata は終了せず、通常ヒープ割当に進む。Linux のページ補充失敗は pool 内の失敗状態を記録して補充を止めるが、専用のエラー文言はない。[`generate.cpp:13032-13045`](../../../../Niko1221/Strata/src/program/generate.cpp)、[`conversation_segment_pool.hpp:196-200`](../../../../Niko1221/Strata/include/strata/core/conversation_segment_pool.hpp)

`docs/DETAILS.md` にはこの環境変数や segment pool の仕様・測定値に対応する記載を確認できなかったため、測定値は記載しない。

## 根拠

- [`src/program/generate.cpp:514-529`](../../../../Niko1221/Strata/src/program/generate.cpp): 値の読み取り、変換、既定値の説明。
- [`src/program/generate.cpp:12934-13045`](../../../../Niko1221/Strata/src/program/generate.cpp): serve/cache 予算、pool の導入、補充、ログ。
- [`include/strata/core/park_pool_policy.hpp:18-40`](../../../../Niko1221/Strata/include/strata/core/park_pool_policy.hpp): 自動サイズと補充許可。
- [`include/strata/core/conversation_segment_pool.hpp:28-93,105-123,134-236`](../../../../Niko1221/Strata/include/strata/core/conversation_segment_pool.hpp): OS 実装、pool の境界、割当・補充・縮小。
- [`include/strata/core/conversation_buffer.hpp:18-30,37-39,150-162`](../../../../Niko1221/Strata/include/strata/core/conversation_buffer.hpp): conversation segment の pool 優先割当と heap fallback。
- [`include/strata/core/conversation_cache.hpp:266-282,406-420`](../../../../Niko1221/Strata/include/strata/core/conversation_cache.hpp): cache 有効条件と pool idle bytes の予算処理。
