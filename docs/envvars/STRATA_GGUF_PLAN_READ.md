# `STRATA_GGUF_PLAN_READ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL prefill の expert stream plan を組み立てるとき、`GgufExpertSource` を stager worker から直接読む経路を使うか、計画を組むスレッドで `blob()` を呼ぶ経路へ切り替える診断用スイッチである。`1` で `gsrc` を `nullptr` にし、`stream_all` 中の各 expert について計画構築中に `m.src->blob(l, e)` を呼ぶ。未設定または `1` 以外では、`m.src` が `GgufExpertSource` の場合に stager job が `read_into()` を呼び、stager worker が GGUF から読み込む。これは読み取り経路と時期の変更であり、環境変数自身が expert の選択や数値計算を指定するものではない。実装は `engine/sycl/src/prefill/prefill.cpp` の `Prefill::run_impl` にある。 (`engine/sycl/src/prefill/prefill.cpp:2692-2699`, `3143-3171`)

通常の `--stream-experts` 経路は SYCL の native (IQ) pack と `--native SHARD1` を必要とし、`GgufExpertSource` がその GGUF を開く。SYCL 以外の backend にはこの読み取り箇所がない。 (`engine/sycl/src/program/generate.cpp:4711-4725`; 候補名の全参照は `engine/sycl/src/prefill/prefill.cpp:3143` のみ)

## 値と判定

値は `std::getenv` で読み、返された文字列の先頭 1 byte が文字 `'1'` かだけを見る。整数変換・文字列全体の比較・空白除去はしない。 (`engine/sycl/src/prefill/prefill.cpp:3143`)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL `Prefill::run_impl` | `plan_reads=false` | `1`, `10`, `1anything`（先頭が `'1'`） | 空文字、`0`, `true`, `false`, `01`, ` 1` |

未設定と空文字はどちらも false。`'1'` で始まる値は後続文字にかかわらず true、それ以外は false で、無効値に対する警告や fallback 処理はない。CLI 引数や別の環境変数で `plan_reads` 自体を上書きするコードはない。 (`engine/sycl/src/prefill/prefill.cpp:3143-3144`)

## 有効になる条件

- `Prefill::run_impl` がこの static 初期化行に到達する必要がある。値は関数内 `static const` に一度保存されるため、初回評価後にプロセス環境を変更しても反映されない。初回評価は prefill 呼び出し時であり、プロセス起動時ではない。 (`engine/sycl/src/prefill/prefill.cpp:2692-2699`, `3143`)
- 実際に読み取り経路が変わるのは、`m.src` が `GgufExpertSource` で、さらに `stream_all` が true のとき。`stream_all` は `m.ring > STAGE`、チャンク `T >= stream_all_min()`、`m.src != nullptr` が条件。満たさない呼び出しでも static 値は初期化されうるが、この変数による `gsrc` の差は expert 計画に使われない。 (`engine/sycl/src/prefill/prefill.cpp:199`, `215-217`, `3090`, `3143-3145`)
- ring が `STAGE` より大きくなるかには、`STRATA_PREFILL_RING`、`STRATA_PREFILL_STREAM_ALL`、`STRATA_PREFILL_STREAM_MIN`、非 resident expert の割合などが関係する。とくに `STRATA_PREFILL_STREAM_ALL=0` は stream-all を止め、`=1` は有効化する。これらの条件で stream-all が無効なら、この変数が有効値でも対象経路を切り替えない。 (`engine/sycl/src/prefill/prefill.cpp:291-323`)
- 通常の生成経路で `GgufExpertSource` が `m.src` になるのは `--stream-experts` かつ `--mmap-experts` ではなく、native pack と `--native` shard がある場合。条件を満たさない場合は起動時に `strata generate` のエラーを出して終了するため、この prefill 経路には進まない。 (`engine/sycl/src/program/generate.cpp:4711-4725`)

## 実行時の詳細

変数が unset または先頭が `1` 以外なら、`dynamic_cast` が成功する `GgufExpertSource` を `gsrc` に保持する。stream-all の計画ループは各対象 expert を `Stager::Job` に登録し、その後の stager worker が `gsrc->read_into()` を呼ぶ。`read_into()` は expert の gate/up/down の3領域を `pread` で宛先 buffer に読み、要求サイズ不足や読み取り失敗などで false を返す。 (`engine/sycl/src/prefill/prefill.cpp:3143-3165`, `engine/sycl/src/prefill/prefill.cpp:553-590`, `engine/sycl/src/core/gguf_expert_source.cpp:224-243`)

先頭が `1` なら `gsrc` は null となり、stream-all の計画ループは `m.src->blob()` をその場で呼ぶ。`GgufExpertSource::blob()` は mirror に該当 expert があればその pointer を返し、そうでなければ GGUF の3領域を `pread` して内部 ring buffer に組み立てる。返された blob が direct DMA の対象でなければ、その pointer とサイズが stager job に保存され、worker が後で `memcpy` する。従ってこの設定は GGUF の読み取りを計画作成側へ移し、worker の `read_into()` 経路を使わない。 (`engine/sycl/src/prefill/prefill.cpp:3163-3186`, `engine/sycl/src/core/gguf_expert_source.cpp:84-120`)

`blob()` が使う内部 ring は `open()` 時に `kRing` 個で作られ、miss の読み込みごとに次の slot を再利用する。いっぽう stream plan はその戻り pointer を `seq` に保持し、後で発行する。したがってこの分岐では、読み込み中に worker の `read_into()` が使う宛先 buffer へ直ちに固定する方式と pointer の寿命が異なる。コードから断定できるのはこの構造までであり、この環境変数での出力同一性や性能は資料・測定から確認できない。 (`engine/sycl/src/core/gguf_expert_source.cpp:59-62`, `84-120`; `engine/sycl/src/prefill/prefill.cpp:3163-3193`)

## ログと測定値

この環境変数を有効にした／無効にしたこと自体を示すログはない。`blob()` が null を返した場合は prefill が `prefill: expert source has no blob` を `err` に設定して false を返す。通常の `gsrc->read_into()` 経路で読み込みに失敗した場合は stager worker が `prefill: reading expert %d of layer %d from the GGUF failed` を stderr に出し、宛先 buffer をゼロ埋めして続行する。後者のメッセージは `plan_reads=true` の経路では使われない。 (`engine/sycl/src/prefill/prefill.cpp:3169-3171`, `578-582`)

この変数の比較測定値は `docs/DETAILS.md` に見つからなかった。コメントにある `stream_all` 一般の測定値は当該フラグを比較したものと確認できないため、ここでは本変数の性能値として扱わない。 (`engine/sycl/src/prefill/prefill.cpp:201-205`, `311-323`)

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:2692-2699` — SYCL prefill の `run_impl`。
- `engine/sycl/src/prefill/prefill.cpp:199-217`, `291-323`, `3090` — stream-all の chunk/ring 条件と関連設定。
- `engine/sycl/src/prefill/prefill.cpp:3143-3195` — 環境変数判定、`gsrc` 選択、計画構築と stager 起動。
- `engine/sycl/src/prefill/prefill.cpp:469-479`, `553-590` — stager job と worker の動作、失敗時のログ。
- `engine/sycl/src/core/gguf_expert_source.cpp:37-63`, `84-120`, `224-243` — GGUF source の ring、`blob()` と `read_into()`。
- `engine/sycl/src/program/generate.cpp:4711-4725` — 通常の `--stream-experts` 経路。
