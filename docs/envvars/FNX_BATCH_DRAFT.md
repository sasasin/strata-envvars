# `FNX_BATCH_DRAFT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX の `BatchDecoder` が draft layer の予測を複数 lane まとめて処理する経路を選ぶスイッチです。有効時、MTP mode の draft 処理は `draft_batched()` に進み、複数 lane の draft layer 推論を `Engine::draft_lanes()` に渡します。無効時は lane ごとに `draft_one()` を呼ぶ経路です（`src/split/src/batch.cpp:325-369,373-414`）。

この環境変数を読む実装は `BatchDecoder` のコンストラクター内にある 1 箇所です。候補一覧にある名前は実際に読み取られています。`FNX_BATCH_DRAFTS` は別の設定で、バッチ decoder の mode を選びます。

## 値と判定

値は `env_int()` を通じて符号付き 10 進整数として読み、結果が 0 かどうかで判定します。文字列全体が整数でなければエラーです。未設定時の既定値だけがビルドで異なります（`src/split/src/batch.cpp:71-75`）。

| ビルド | 未設定時 | 整数 0 | 0 以外の整数 |
|---|---:|---|---|
| `FNX_HIP` が有効な HIP build | 1（有効） | 無効 | 有効 |
| それ以外の build | 0（無効） | 無効 | 有効 |

`env_int()` は `std::getenv()` で値を取得し、符号（任意）と 10 進数字からなる文字列を `std::strtoll(..., 10)` で `long long` に変換します。先頭・末尾の空白、空文字、数字以外の末尾、10 進整数でない表記、`long long` の範囲外は受け付けず、`<変数名>: '<値>' is not a whole number` の例外になります。`0` と `-0` は無効、`+1`、`-1`、`2` などは有効です。0 以外の値に追加の範囲制限はありません（`src/split/src/env.hpp:15-21,33-40`）。

## 有効になる条件

`FNX_BATCH_DRAFT=1` 相当の値でも、`BatchDecoder::draft_next()` が `mode_ == BatchDrafts::mtp` と判定し、かつ次の window に進む lane がある場合にだけ batched draft 処理の分岐に到達します。`FNX_BATCH_DRAFTS=lookup` では MTP mode ではないため、この変数による分岐は使われません。`FNX_BATCH_DRAFTS=0` では sfnx は decoder を作らず、`fnx_run bdecode` は診断メッセージを出して終了します。unset または `FNX_BATCH_DRAFTS=1` は MTP mode です（`src/split/src/engine_common.cu:1020-1028`; `src/split/src/batch.cpp:261-265,325-328`; `src/split/tools/sfnx.cpp:443-445`; `src/split/tools/fnx_run.cpp:646-657`）。

主な呼び出し経路は、複数 slot の sfnx（`a.batch > 1`）と `fnx_run` の `bdecode` / `batch` です。sfnx は `Server` 作成時に decoder を作り、`decode_step()` で lane 群の window を処理します。`fnx_run bdecode` は mode 確認後に MTP と Engine を作成して decoder を構築します。通常の単一 lane `Session` 経路にはこの `BatchDecoder` 分岐はありません（`src/split/tools/sfnx.cpp:435-445,572-607`; `src/split/tools/fnx_run.cpp:646-670`; `src/split/tools/batch_check.hpp:80-90`）。

batched 経路が実際に `Engine::draft_lanes()` を実行するには、Engine に draft layer が attach され、window の row state があり、pending window が commit 済みである必要があります。満たさない場合は `draft_lanes()` が `no draft layer attached`、`no window has run`、または `a window is not committed` などの `std::runtime_error` を投げます。sfnx と `fnx_run bdecode` は decoder より前に MTP を Engine に attach しています（`src/split/src/engine_common.cu:1489-1493`; `src/split/tools/sfnx.cpp:1055-1059`; `src/split/tools/fnx_run.cpp:654-657`）。

## 実行時の詳細

環境値は `BatchDecoder` のコンストラクターで読み込まれ、メンバー `batched_draft_` に保存されます。`env_int()` 自体に cache はありませんが、この decoder は各経路で起動時に作られ、以後の `draft_next()` は保存済み bool を参照します。稼働中に環境値を変えても既存 decoder には反映されず、新たな `BatchDecoder` を作る場合に再評価されます（`src/split/src/batch.cpp:64-85,325-328`; 呼び出し箇所は `src/split/tools/sfnx.cpp:443-445` と `src/split/tools/fnx_run.cpp:669`）。

有効時の `draft_batched()` は進行中 lane の draft request をまとめて作り、`Engine::draft_lanes()` で最初の draft を得ます。必要な chain draft も lane 群の row としてまとめて処理します。無効時は `draft_next()` 内で lane ごとに `draft_one()` を実行します（`src/split/src/batch.cpp:325-369,373-460`）。この環境変数自体について、有効化ログは確認できません。無効な文字列のときは例外が呼び出し元へ伝わり、`fnx_run` は stderr に `fnx_run: <例外内容>` を出して status 1、sfnx は `fail()` が `ERR <例外内容>` を `say()` に渡し、stderr に `sfnx: failed: <例外内容>` を出して status 1 で終了します（`src/split/tools/fnx_run.cpp:1364-1373`; `src/split/tools/sfnx.cpp:1030-1035,1064-1095`）。

ソースコメントには HIP での性能測定値に触れた記述がありますが、調査範囲では条件を記した資料を確認できなかったため、性能値や一般的な速度効果は記載しません。
