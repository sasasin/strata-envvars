# `QSA_MROPE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前を環境から読むのは、Metal カーネルの検証・ベンチ用プログラム `qsa_parity` だけです。QSA の `qsa_prep` に M-RoPE 用 function constant 24 を渡し、同じモードを CPU 参照計算でも使って結果を照合します。通常の Strata エンジン、サーバー、CLI の実行時設定として読む箇所は見つかりませんでした。

## 値と判定

| 環境値 | 検証プログラムの扱い |
|---|---|
| 未設定 | M-RoPE を無効にする。function constant 24 は `false`。 |
| 設定あり（空文字を含む） | M-RoPE を有効にする。値が文字列全体で `id` と一致すると恒等位置テーブルを使い、それ以外はセルごとに乱数生成した `(t, h, w)` 位置テーブルを使う。 |

`1` など特定の真偽文字列への parse はありません。設定有無は `getenv(...) != nullptr` で判定し、`id` の場合だけ `std::string(mre) == "id"` で完全一致比較します。大文字小文字や前後空白を正規化しません。CLI 引数による上書きや、他の環境変数との優先順位はありません。

## 有効になる条件

この動作は `metal/tests/qsa_parity.cpp` の `qsa_parity` を実行した場合に限られます。`metal/CMakeLists.txt` は `tests/*.cpp` から個別実行ファイルを作り、このファイル名から `qsa_parity` を生成します。Metal プロジェクトは macOS 専用です。Metal カーネル側の同名 `QSA_MROPE` は環境変数ではなく、ホストが function constant 24 に設定するコンパイル時定数です。

## 実行時の詳細

プログラム起動時、pipeline 作成時に環境変数の設定有無を読み、続いて M-RoPE モードと `id` モードを読み取ります。読み取り結果を後から再評価する処理はありません。M-RoPE 有効時はテスト用テーブルを `qsa_prep` に渡し、CPU 側も同じテーブルを参照して Q/K/indexer の RoPE と pooled key を照合します。`id` は恒等テーブル、その他の設定値は乱数テーブルです。

この変数専用のログやエラー分岐はありません。通常の `qsa_parity` は各段階の照合結果を `PASS` / `FAIL` として出力し、いずれかが失敗すると最後に `SOME FAILED` を出して終了コード 1、すべて通ると `ALL PASS` を出して 0 を返します。失敗がこの変数に起因するかを示す専用ログはありません。`--bench` 経路ではカーネル時間を表示して終了し、parity の照合は行いません。

## 根拠

- `metal/tests/qsa_parity.cpp:30-47` は CLI 引数と環境変数判定、pipeline への function constant 24 の設定。
- `metal/tests/qsa_parity.cpp:69-79,171-184` は `id` / 乱数テーブルの選択と CPU 参照での M-RoPE 計算。
- `metal/tests/qsa_parity.cpp:216-220,302-307` は照合結果、最終表示、終了コード。
- `metal/CMakeLists.txt:1-17,41-48` は Metal 専用プロジェクトと `tests/*.cpp` の実行ファイル生成。
- `metal/kernels/qsa.metal:31-37,92-104` は function constant 24 の宣言と `qsa_prep` の引数。
- `docs/QWEN36.md:39-41` と `docs/DETAILS.md:987-989` は画像入力経路の M-RoPE について説明しますが、`QSA_MROPE` 環境変数の説明ではありません。
