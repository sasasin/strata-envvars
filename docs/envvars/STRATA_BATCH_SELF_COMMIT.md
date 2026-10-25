# `STRATA_BATCH_SELF_COMMIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Verifier の batch window が「各 row が異なる slot に属する」場合に、window 内で各 slot の GDN 状態などを進め、後続の batch commit graph を省略します。batch 処理自体を有効にする変数ではなく、batch window の行構成が条件に合う場合の commit 方法を変える opt-in です。

## 値と判定

`env_on()` は環境変数が設定され、かつ空文字でなく、先頭文字が `0` でない場合に true を返します。文字列全体や数値としての妥当性は調べません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0` または `0anything` | 無効 |
| `1`, `2`, `true`, `false`, `anything` | 有効（先頭文字が `0` でないため） |

大文字小文字、空白、後続文字は判定に影響しません。環境変数は `src/core/verify.cpp` のグローバル `const bool` 初期化時に読み取られ、その値をプロセス内で使います。実行中の環境変更を再読込するコードはありません。

根拠: `src/core/verify.cpp:220-223,228-236`。

## 有効になる条件

- CUDA/HIP 側の `src/core/verify.cpp` にある Verifier の batch 処理経路で使われます。別実装の `sycl/src/core/verify.cpp` にはこの変数の参照がなく、同じ挙動を確認できません。
- batch window に渡される全 row の slot 番号が相異なる必要があります。実装は全ての row の組を比較し、`S >= 1` も確認します。
- 値が有効でも row 番号が重複する window では通常の batch commit graph を使います。
- この変数は batch window の生成や slot 数を決めません。batch window が capture / launch される経路に入った場合にだけ作用します。

根拠: `src/core/verify.cpp:243-250,3345-3350,3370-3372,3790-3800`。

## 実行時の詳細

batch window の graph capture 中、`record_window()` は `batch_rec_` と row の slot 番号を使って `keep_rows` を決めます。これが true なら GDN convolution と recurrence の処理へ row を保持する指定を渡し、PLE history と QSA indexer tail の commit 用 snapshot を省きます。各 row は異なる slot の状態を window 内で進めます。

その後の `capture_commit_batch()` は commit graph の capture を省略します。通常の batch launch でも window graph の後に commit graph を launch せず、`commit_slot_prefixes()` も commit graph の launch と同期を省きます。PLE stage では host 側の `ple_prev` 更新は引き続き行われます。変数が無効、または slot 番号が重複する場合はこれらの省略分岐を通らず、通常の commit graph 経路です。

初期化ログは batch slot 数と layer range を出力し、この変数が有効なら末尾に `, one-row windows keep their rows` を付けます。環境変数そのものの parse error や無効値警告はありません。

根拠: `src/core/verify.cpp:1106-1110,1265-1279,1399-1409,1460-1470,1561-1568,3333-3335,3370-3372,3754-3772,3797-3800`。

## 文書との照合

`docs/BATCHING.md:110-123` はこの変数を opt-in とし、「one-row-per-slot window advances the GDN state itself, no commit graph」と説明しています。ソースでは GDN のほか PLE history と QSA indexer tail の snapshot / commit graph 処理にも条件分岐があります。同資料の測定表は複数の batch switch をまとめた比較のため、この変数単独の性能効果を示すものとしては扱いません。
