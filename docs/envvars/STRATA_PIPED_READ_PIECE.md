# `STRATA_PIPED_READ_PIECE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

layer split 上で `--batch-groups` により slot group を複数 stage にパイプライン実行しているとき、prompt の読み込みを何 token ずつの区間に分けるかを指定します。各区間の終わりでパイプラインを drain し、待機中の短い要求に slot を譲る機会を設けます。slot が稼働中なら、区間の後に decode も進めます。

## 値と判定

`read_part` 内で最初にこの値が必要になったときに `std::getenv` と `std::atoi` で読み、`static const int64_t` に保存します。未設定は `0`、設定時は `max(0, atoi(value))` です。`atoi` は整数全体の厳密な検証をしないため、先頭の空白と符号の後の数字列を変換し、数字列の後ろは無視します。空文字、数字で始まらない文字列、`0`、負値は 0 になり、たとえば `12tail` は 12 として扱われます。オーバーフロー値の扱いはこのコードで検査・規定されていません。

| parse 結果 | 区間長と動作 |
|---|---|
| 0（unset、空、無効な先頭、0、負値など） | opt-in 無効。pipelined groups の prompt は従来どおり一度に読み込む |
| 正数 N | 有効条件を満たす場合、prompt chunk の倍数に切り下げ、1〜32 chunk に制限した長さで読む |

chunk 長 `C` は、prompt plan がある場合は `max(1, sp.chunk() / plan.chunk)` 個の plan chunk、ない場合は `max(sp.chunk(), 1)` です。実際の区間長は `clamp(N / C, 1, 32) * C` です。このため `N < C` でも 1 chunk、非常に大きい N でも最大 32 chunk になります。入力値 N は chunk 境界に合わせるため切り下げられます。

## 有効になる条件

- `--batch` が正、`--batch-groups` が 1 より大きく、layer split の stage 数が 1 以上であること（`piped`）。
- `STRATA_PIPED_READ_PIECE` の保存済み parse 値が正であること。
- 対象が `read_part` を通る prompt read であること。window merge など `read_windows` になる部分にはこの分割を適用しません。

変数が正でも `piped` が偽なら `pr_on` は偽です。このとき同じコード内の既存 `batch_read_piece` 規則へ進み、変数による pipelined read 分割は行いません。値の有効条件判定は `read_part` 内ですが、static 値はプロセス中で初回評価後に再利用されるため、起動後に環境値を変更しても再評価されません。

## 実行時の詳細

区間ごとに `run(q, r)` を実行し、planned read では各 run に同一の plan chunk を強制します。区間の最後で slot group の in-flight pipeline を drain します。区間の間に `BYIELD` が届いており、`give_way` の条件を満たす場合は、読み込み済みの部分を slot に保持させて短い要求へ譲ります。譲らない場合、slot が decode 中なら `STRATA_BATCH_DECODE_SHARE` と区間の read 時間から decode budget を計算し、slot groups を pipeline 経由でその時間だけ進めてから再度 drain します。上限・下限はそれぞれ `STRATA_PIPED_DECODE_MAX_MS` と `STRATA_PIPED_DECODE_MIN_MS` が担います。これらは本変数とは別の設定です。

連続して prompt read が到着した場合、前の piecewise read 終了から 1 秒以内（decode budget 分を加算）の開始なら、次の読み込み前に slot decode の lead-in を実行する経路があります。stderr には piece ごとの `strata batch: piped read ...`、give-way 時の `the prompt read gives way ...`、lead-in 時の `a read right after a read ...` などが出ます。従来動作として、この変数が unset なら一回の read です。

## 根拠

- `src/program/generate.cpp:12758-12817`: prompt read の `read_part`、chunk/plan の決定。
- `src/program/generate.cpp:13117-13139`: 環境変数の変換・static cache・有効条件・piece 長。
- `src/program/generate.cpp:13140-13159,13160-13179,13181-13245`: decode budget、連続 read の lead-in、区間 read / drain / give-way の流れとログ。
- `src/program/generate.cpp:11092-11100`: `piped` の判定（batch、batch groups、layer split stages）。
- `include/strata/program/batch_read.hpp:56-67`: piece の chunk 丸めと 32 chunk 上限。
- `docs/BATCHING.md:287-310`: 設計説明との照合。ソースの処理と一致する。`docs/DETAILS.md` にこの変数の説明は見当たらず、性能値は本調査では記載しない。
