# `STRATA_SLOT_CKPT_MOVE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`--serve --batch` の slot admission で、現在の会話の turn checkpoint をメインセッションの checkpoint chain から batch slot にコピーする代わりに移動します。コードコメントはコピー対象を約112 MBの host vector としています。移動対象になった checkpoint の内容は slot が保持し、後続リクエストがその会話を続ける際には slot 内の checkpoint も再利用候補になります。

この環境変数を有効にすると、checkpoint pool も有効になります。slot の古い checkpoint の vector storage を次の checkpoint 保存に再利用する経路です。したがって効果は checkpoint の所有場所の移動だけではありません。

## 値と判定

`std::getenv()` の結果が存在し、先頭文字が `'0'` でなければ有効です。数値変換や文字列全体の比較はしません。

| 値 | 結果 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効（設定値へのポインターは存在し、先頭文字は `\0`） |
| `0` または `0` で始まる文字列（例: `0abc`） | 無効 |
| `1`、`true`、`false`、空白で始まる文字列など、`0` 以外で始まる文字列 | 有効 |

判定値は関数内の `static const bool` に保存されます。最初に判定した後でプロセス環境を書き換えても再評価されません。

根拠: `src/program/generate.cpp:218-224`。

## 有効になる条件

- `--serve` の処理内で有効な場合に checkpoint pool が作られます。環境変数を有効にしただけで `--batch` を指定しなければ、slot admission 時の checkpoint 移動は起きません。
- 移動は batch の admission が継続可能で、slot への状態コピーに成功した場合に行われます。コード上の継続条件は、キャンセルされておらず、今回1 tokenを生成し、残り生成数が1より大きく、終了理由が `length` で、`live.size() == p` であることです。
- `checks` から `live` の真の prefix である最長 checkpoint を選びます。選んだ checkpoint が画像を含まず、pinned でなく、別 slot から借りた checkpoint（`best_lent`）でもなく、turn の境界 `turn_at` にあるか、slot から戻してきた `moved_in` checkpoint である場合に限って移動します。
- それ以外の候補 checkpoint は従来どおり slot にコピーされます。候補がない場合も移動しません。
- `--prompt-cache` が0より大きく、control vector 状態が一致し、メインセッションに有効な live state がある場合、slot の checkpoint は再開地点の候補に加わります。slot が active の間に候補にするには `STRATA_SLOT_CKPT_MOVE` が有効で、slot が tainted でないことなどの条件があります。MTP 使用時は batch MTP または admission 処理中など、追加の条件もあります。

根拠: `src/program/generate.cpp:14630-14637,14665-14700,11918-11944,11957-11977`。

## 実行時の詳細

環境変数の判定は `slot_ckpt_move_env()` に集約されています。serve loop の `CheckpointPool` は `STRATA_CKPT_POOL` または `STRATA_SLOT_CKPT_MOVE` のどちらかが有効なら有効になります。slot admission では slot の古い checkpoint を pool に渡し、上記の選択条件を満たす turn checkpoint は `std::move` と元 vector からの erase で slot に移します。条件を満たさない checkpoint は pool の storage を使ってコピーする経路、または通常コピーになります。

移動後、slot が保持する checkpoint は次の request の prompt cache 探索で調べられます。slot 自身に戻ってくる会話を再開する場合は checkpoint を slot から `checks` に戻し、`moved_in` として記録します。その request が再び batch admission されると、同じ checkpoint は上記条件を満たせば slot に移ります。checkpoint の復元に失敗した場合は `ERR restoring a conversation checkpoint failed` を stdout に出して serve 処理を終了する経路があります。

変数専用の有効化ログはありません。admission の通常ログは `strata batch: slot ... takes ...` です。`STRATA_TRACE` が有効な場合、admission の詳細行末に移動が起きたときだけ ` (moved)` が付きます。slot から会話を再開した場合、stderr に `strata batch: slot ... gave back ... tokens of this conversation (its turn checkpoint)` と出ます。

根拠: `src/program/generate.cpp:8775-8778,12131-12145,12326-12335,14703-14717`。

## 文書との照合

`docs/BATCHING.md:110-119` はこの変数を opt-in とし、admission の turn checkpoint を slot に移すこと、checkpoint pool のように捨てた checkpoint の storage を保持することを説明しています。`src/program/generate.cpp:212-217` も同じ設計を記述しています。性能向上や token の同一性について、この調査では新しい測定をしていません。

## 根拠

- `src/program/generate.cpp:212-224` — 値の判定と読み取り時期。
- `src/program/generate.cpp:191-200,8775-8778` — checkpoint pool の条件。
- `src/program/generate.cpp:11918-11944,11957-11977` — slot checkpoint の再開候補と active slot の条件。
- `src/program/generate.cpp:12131-12145,12326-12339` — slot と main checkpoint chain 間の移動。
- `src/program/generate.cpp:14630-14717` — admission 条件、移動判定、ログ。
- `docs/BATCHING.md:110-119` — 既存文書との照合。
