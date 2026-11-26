# `STRATA_REFILL_PARTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

サーバーの prompt 処理で、prompt 用に一時借用した expert-cache slot を返すときの転送方法を切り替える。1 以外も含め `atoi` の結果が 0 以外なら、非 blocking refill で source が提供できる GGUF の分割範囲を slot の対応 offset へ直接コピーする。分割範囲が得られないとき、またはこの設定を使わないときは、`blob_stable` が返す組み立て済み blob を使う既定経路に戻る。どちらも同じ借用 slot に expert を戻し、resident table を更新する処理であり、この分岐は expert の計算や選択を変更しない（`engine/src/program/generate.cpp:20488-20518`）。

## 値と判定

`generate.cpp` 内の関数ブロックにある関数ローカル `static` を初期化する際、`std::getenv` と `std::atoi` で一度だけ読み取る。環境変数が未設定なら無効。空文字や数値で始まらない文字列も `atoi` が 0 を返すため無効。数値として先頭から変換できた整数が 0 以外なら有効で、後続文字列は検査されない。符号と先頭空白は `atoi` の変換規則に従う。値域検査や clamp はなく、`atoi` の整数範囲を超える入力の結果は保証されない（`engine/src/program/generate.cpp:20497`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の refill 判定 | 無効 | `1`、`-1`、`2`、`1junk`、` 1` | 空文字、`0`、`0anything`、`true`、`false`、`junk` |
| `STRATA_REFILL_BLOCKING` が設定済み | 分割転送を使わない | 該当なし | `STRATA_REFILL_PARTS` の値にかかわらず分割転送を使わない |

## 有効になる条件

- borrowed slot の refill が実行される prompt 経路であること。prompt の windows を読む前と prompt 読み込み完了後に refill する（`engine/src/program/generate.cpp:20488-20490`, `21551-21558`, `21624-21628`）。
- `STRATA_REFILL_PARTS` の読み取り結果が有効で、かつ `STRATA_REFILL_BLOCKING` が未設定であること。後者は値ではなく設定有無で判定し、空文字でも blocking 扱いになる（`engine/src/program/generate.cpp:674-677`, `20502-20506`）。
- `srcp->blob_parts(...)` が 1 個以上の分割を返すこと。`FileExpertSource` では mapped-in-place の GGUF が対象で、role mapping があり、direct source・I/O prefetch・unmapped 状態ではなく、該当 expert が resident complement や override にない場合に分割を返す。それ以外は 0 を返して従来経路へ進む（`engine/src/core/expert_source.cpp:5181-5197`）。別種の `ExpertSource` の標準実装も 0 を返す（`engine/include/strata/core/expert_source.hpp:214-218`）。
- `fill_slot_queued_parts` が分割を slot に収められること。分割合計または最大 offset が slot 容量を超える場合は失敗する（`engine/src/core/expert_cache.cpp:922-936`）。

読み取り箇所とコピー箇所に OS・GPU backend・build macro による明示的な guard はない。コード上の適用範囲は GPU backend 名ではなく、refill 経路、source が返す分割範囲、blocking 設定で決まる。ソースコメントでは gfx1151 の表を使う値として案内されているが、コードに gfx1151 専用の制限はない（`engine/src/program/generate.cpp:20495-20497`）。CLI 引数や他の設定値による `STRATA_REFILL_PARTS` 自体の上書きもない。

## 実行時の詳細

値は上記のコードブロックへ初めて到達したときに初期化され、以後プロセス内で cache される。実行中に環境を変更しても判定は変わらない。refill ごとに、まず各 lent expert の分割範囲を問い合わせる。有効な分割があれば `fill_slot_queued_parts` で各範囲を対応 offset に非同期コピーし、その slot を `host_res` に戻す。分割が取れなければ `blob_stable` で blob を得て、`STRATA_REFILL_BLOCKING` の状態に応じて blocking または queued の通常コピーを行う。refill 後は queued copy を同期し、借用状態を消し、resident table を upload する（`engine/src/program/generate.cpp:20497-20518`, `20520-20568`; 分割コピーと同期: `engine/src/core/expert_cache.cpp:922-963`）。

複数 stage で slot を借りている場合は、`STRATA_REFILL_SERIAL` が未設定なら全 stage の copy を先に queue してから待つ。設定されていれば stage ごとに refill と待機を行う。この設定は `STRATA_REFILL_PARTS` の値を変えない（`engine/src/program/generate.cpp:20543-20560`）。Windows では copy 完了後に各 mapped expert を release する（同 `20520-20529`）。

## ログと測定値

通常の成功時に `STRATA_REFILL_PARTS` 専用のログはない。`STRATA_TRACE` が設定され、lent slot がある場合は stderr に `strata trace: refill start ...` と、成功した refill の slot 数・stage 数・時間を示す `strata trace: refilled %lld slots on %lld stage(s) in %.1f ms` が出る。これは分割コピーを使ったかどうかを区別しない（`engine/src/program/generate.cpp:16069-16078`, `20498-20499`, `20561-20567`）。

refill が失敗すると stdout に `ERR refilling a lent slot failed: %s` を出してその処理を終了する。分割が slot に収まらない場合や queued copy / 同期が失敗した場合もこの経路に伝わる（`engine/src/core/expert_cache.cpp:922-963`; `engine/src/program/generate.cpp:21555-21557`, `21624-21628`）。

`docs/STRIX_HALO.md:159,241` は gfx1151 での測定として、UD-Q4_K_XL / UD-IQ4_XS の prompt 4K–8K で +2.3–3.5%、32K で +1.1% と記載する。表には測定機材・OS・試行条件の詳細がないため、この値を他環境の性能予測には使えない。

## 根拠

- `engine/src/program/generate.cpp:20488-20518` — `STRATA_REFILL_PARTS` の読み取り、分割範囲の選択、slot refill。
- `engine/src/program/generate.cpp:20520-20568` — 完了待ち、複数 stage の処理、trace ログ。
- `engine/src/program/generate.cpp:21551-21558,21624-21628` — refill 呼び出しと失敗時の出力。
- `engine/src/core/expert_source.cpp:5181-5197` — `FileExpertSource::blob_parts` の提供条件。
- `engine/src/core/expert_cache.cpp:922-963` — 分割範囲の転送、境界検査、同期。
- `engine/include/strata/core/expert_source.hpp:214-218` — 分割を返さない source の標準動作。
- `docs/STRIX_HALO.md:159,241` — 測定値の記載。
