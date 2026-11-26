# `STRATA_DF2_PROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

DFlash2 drafter の計測用プロファイルを有効にする。`Dflash2Drafter::make_streams()` がこの変数を読み、値が有効なら `Prof` を確保する。その drafter の draft round は CUDA graph を使わず通常の記録関数を実行し、各 stage の後に event を置く。round ごとの stage 時間を集計し、drafter の破棄時に平均を stderr へ出す。通常のモデル実行全般や verifier のプロファイルを有効にする設定ではない。`engine/src/core/dflash2.cpp:129-135,148-179,296`。

## 値と判定

`std::getenv` の戻り値が非 null で、先頭 1 文字が ASCII の `1` のときだけ有効。文字列全体を数値や真偽値として parse しない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `Dflash2Drafter::make_streams()` が実行されるビルド | 無効（`prof_` は null） | `1`、`10`、`1anything` | 空文字、`0`、`true`、`True`、` 1`、`01`、`2` |

大文字小文字・空白の正規化、文字列全体の数値妥当性検査、範囲検査はない。`1` の後ろに何が続いても先頭が `1` なら有効。未設定と空文字はいずれも無効だが、前者は null、後者は先頭文字が終端文字となるため条件を満たさない。`engine/src/core/dflash2.cpp:296`。

## 有効になる条件

- 実行経路が DFlash2 drafter を生成して `make_streams()` まで進む必要がある。通常の generate 経路では `STRATA_HAVE_DFLASH2` が定義された build で DFlash2 分岐がコンパイルされ、`--draft dflash2` または `--draft auto` の DFlash2 選択後に `df2.load()` が呼ばれる。CUDA/HIP 共通 build は同 macro を定義し DFlash2 ソースを `strata_engine` に含める。`engine/cmake/strata_gpu_engine.cmake:8-13,310-313`、`engine/src/program/generate.cpp:8266-8275`。
- `load()` が stream/event 作成まで成功しなければ profile 設定行に到達しない。`make_streams()` の呼び出し元は `load()` と `clone_alloc()`。後者は batch slot 用 drafter を複製する経路で、各インスタンスが独立して環境値を判定する。`engine/src/core/dflash2.cpp:187-192,267-268,271-302,658-666`。
- `--draft auto` では要求・ルールにより選ばれた drafterが DFlash2 である場合に限る。MTP のみを使う実行ではこの変数は参照されない。`engine/src/program/generate.cpp:1184-1192,8266-8275`。
- OS やサーバーモード専用の分岐は読み取り箇所にない。ビルドが DFlash2 実装を含み、実行時に DFlash2 drafter が作成されることが条件。

## 実行時の詳細

環境値は `make_streams()` が drafter ごとに呼ばれるときに一度読み、そのインスタンスの `prof_` に保存される。`load()` は `make_streams()` の後に `alloc()` へ進む。clone も `clone_alloc()` の中で同じ処理を通る。したがって各 drafter の stream 作成時点の値が使われ、同じインスタンスの実行中に環境値を変えても設定は更新されない。関数内 `static` cache ではない。`engine/src/core/dflash2.cpp:187-189,267-268,271-302,658-666`。

有効時、`prepare()` は graph capture をせず成功扱いで戻る。また `draft_launch()` は各 round で event を付けながら `record_context()` と `record_block()` を直接実行し、`prof_collect()` が stream を同期して前後 event の経過時間を stage 名ごとに加算する。stage event の名前には `df2_attention`、`gemm:fc`、`native_mmvq` などがある。context 呼び出しで記録した event は round 開始時に破棄・クリアされ、round 内の値として集計されない。`engine/src/core/dflash2.cpp:148-170,493-618,752-763,1170-1209`。

`draft_finish()` は stream 同期後も通常どおり draft token と確率を出力先へコピーし、round 数を加算する。コードは profile 有効時に別の token 選択規則を設定していない。`engine/src/core/dflash2.cpp:1218-1240`。

## ログと測定値

少なくとも 1 round の集計があれば、`Dflash2Drafter` のデストラクタで次の形式を stderr に出力する（stage 項目は実行されたもの）。round 数が 0 の場合は出力しない。

```text
strata dflash2 profile (<rounds> rounds, ms per round, total <sum>): <stage> <average-ms> ...
```

文字列の書式は固定小数点 3 桁。stage ごとの累計時間を `rounds` で割り、`total` は stage 平均の合計として出す。CUDA event の作成・記録・同期を伴う計測であり、graph 実行時の測定値ではない。Strata の資料にこの変数による測定値は確認できない。`engine/src/core/dflash2.cpp:40-44,157-179`。

## 根拠

- 全参照と判定、stage event、集計、出力: `engine/src/core/dflash2.cpp:129-179,296`
- DFlash2 build と generate 経路: `engine/cmake/strata_gpu_engine.cmake:8-13,310-313`、`engine/src/program/generate.cpp:8266-8275`
- graph を使わない profile 経路と round 完了: `engine/src/core/dflash2.cpp:621-656,752-763,1170-1240`
