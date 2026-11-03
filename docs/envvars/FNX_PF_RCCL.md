# `FNX_PF_RCCL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

AMD HIP 版の同梱 `strata-split` エンジンで、prompt prefill 中にカード間で行う chunk sum を RCCL all-reduce に切り替えます。RCCL の初期化や自己検査が通らない場合、エンジンは host-memory exchange を使う経路に戻ります。通常の `strata` エンジンを含む全実行経路に共通する設定ではありません。

根拠: `src/split/src/engine.cu:86-104`, `src/split/src/prefill.cu:515-535`。

## 値と判定

値は `std::getenv()` で取得され、`rccl_decide()` が環境変数の文字列全体を `"0"` と `strcmp` で比較します。数値 parse や真偽値文字列の検証はしません。

| 値 | 判定 |
| --- | --- |
| 未設定 | `RCCL_DEFAULT_ON`（現行定義は `true`）を使う。peer push が利用可能なら RCCL を試す。 |
| 厳密に `0` | OFF。RCCL のロード・初期化を行わず、host exchange を使う。 |
| その他の設定値 | ON 扱い。例: 空文字、`00`、`1`, `false`, ` 0`。ただし peer push が OFF なら RCCL は使われない。 |

空文字を含め、`"0"` 以外の設定値に形式検証や範囲検査はありません。CLI 引数による上書きはこの判定経路にありません。

根拠: `src/split/src/hip/rccl_dl.hpp:19-20,67-82`, `src/split/src/engine.cu:95-103`。

## 有効になる条件

- 対象は `STRATA_BUILD_SPLIT=ON` で作る同梱 split engine の HIP build です。ビルド定義 `FNX_HIP=1` の経路でのみ `FNX_PF_RCCL` の読み取りと RCCL 設定がコンパイルされます。split engine 自体は Linux の HIP または CUDA 向けオプション機能です。CUDA build ではこの RCCL 分岐がなく、変数を読みません。
- `FNX_PEER` の判定で peer push が有効になっている必要があります。`FNX_PEER=0`、または peer probe に失敗した場合は RCCL を使いません。対象変数が明示設定されていて peer push が OFF の場合は、RCCL を使わない旨を stderr に出します。未設定時の既定 ON だけで試みた場合はこの理由行を出しません。
- RCCL を試みるとき、共有ライブラリのロード、必要な関数の解決、communicator 作成、HIP buffer/stream 作成、および all-reduce の自己検査が成功する必要があります。失敗時は stderr に理由を含む一行を出し、host exchange に戻ります。
- `FNX_RCCL_LIB` が空でない場合は Strata の loader がその値をライブラリ名・パスとして使います。未設定または空文字なら `librccl.so.1` をロード対象にします。

根拠: `src/split/CMakeLists.txt:20-27,68-109`, `src/split/src/engine.cu:86-104`, `src/split/src/hip/peer_policy.hpp:25-40`, `src/split/src/hip/rccl_dl.hpp:32-58,67-82`, `src/split/src/hip/rccl.h:39-124`。

## 実行時の詳細

値は `Engine` の構築時に一度読み、`rccl_on_` と `rccl_` に保持されます。プロセス中の後続 prefill ごとにこの変数を読み直す処理はありません。環境の変更を実行中に反映する仕組みもありません。

RCCL が有効なら、`prefill_alloc()` がカードごとの prefill state に API と communicator を設定します。`pf_ring()` は prompt chunk の各 sum を RCCL の in-place all-reduce に渡し、通常の ring copy-engine 経路を通りません。標準設定では f16 に pack した buffer を all-reduce してから f32 に戻します。関連設定 `FNX_PF_RCCL_F32` が非ゼロなら f32 の行を直接 all-reduce します。この補助変数は RCCL が有効な場合にだけ `prefill_alloc()` で参照されます。RCCL を使わない場合は `pf_ring_run()` の host-memory exchange に進みます。

起動時の判断ログは `fnx: The prompt sums use RCCL (<library path>).`、peer push 条件不足時は `fnx: RCCL is not used for the prompt sums: the peer push between the cards is off, so the host exchange stays.`、初期化失敗時は `fnx: RCCL is not available here (<reason>): the prompt sums use the host exchange.` の形式です。prefill 実行中に `ncclAllReduce` がエラーを返すと `prefill: ncclAllReduce: <RCCL error>` の例外、collective group の終了がエラーを返すと `prefill: ncclGroupEnd: <RCCL error>` の例外になります。ここでは外部 RCCL 自身の動作は説明対象に含めていません。

根拠: `src/split/src/engine.cu:95-104`, `src/split/src/prefill.cu:515-535,625-626,760-766,1060-1078,1155-1161`, `src/split/src/hip/rccl_dl.hpp:32-40`, `src/split/src/hip/rccl.h:18-25,50-124`。

## 文書との食い違い

この commit の実装では `RCCL_DEFAULT_ON` が `true` で、未設定時も条件が合えば RCCL を試します。しかし `src/split/src/hip/rccl_dl.hpp:20,61-62` のコメントと `docs/SPLIT_ENGINE.md:71` は「既定 OFF」と説明しています。また `src/split/src/engine.cu:95` のコメントも既定 OFF としています。これらの説明と実装は一致しないため、本書では実装の定数と判定コードを現行挙動の根拠としました。

