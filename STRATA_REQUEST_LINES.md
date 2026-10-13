# `STRATA_REQUEST_LINES`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 調査）。外部ライブラリやドライバーの環境変数動作は対象外。

## 役割

Strata Python サーバーがエンジンのログファイルを追跡し、エンジン自身のリクエスト要約行をサーバープロセスの標準出力にも再掲します。標準エラーをログファイルに送っている起動構成で、サーバーの標準出力だけを見る supervisor などがリクエストごとの数値を得る用途です。これはログ表示の追加であり、生成やエンジン計算の設定は変更しません。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字列 | 無効（`os.environ.get()` が `""` を返し、偽として扱われる） |
| 空でない任意の文字列 | 有効。`1` との比較や数値変換はしないため、`0`、`false`、`true` なども有効 |

読み取り箇所は `StrataEngine.__init__` の `os.environ.get("STRATA_REQUEST_LINES")` です。値はコンストラクター実行時に評価され、設定ファイルや CLI 引数との優先順位はありません。

## 有効になる条件

- `StrataEngine` が `lazy=False` で初期化されること。`lazy=True` の初期化は環境変数判定より前に戻ります。
- エンジンの `log` パスが設定されていること。ログがないと follower thread は作られません。
- 当該ログパスについて、同じサーバープロセス内でまだ follower thread を登録していないこと。

通常起動ではログパスを指定して `StrataEngine` を作成し、複数 GPU の replica 起動では replica ごとのログパスで各 engine を作成します（`serve/server.py:6073-6077,6261-6265`）。環境変数は親の Python サーバーで読みます。engine 子プロセスへ渡す `env` の内容をこの判定には使いません。

## 実行時の詳細

有効条件を満たすと、サーバーは `daemon=True` の thread を作成し、初期化時点のログファイル末尾から読み始めます。thread はファイル末尾に達すると 0.2 秒ごとに再読込を試みます。`ENGINE_REQUEST` 正規表現に合う行を見つけると、次の形式でサーバープロセスの標準出力へ出し、flush します。

```text
[strata] request prompt P cached C output O prompt_read R ms total S ms prefill X tok/s decode Y tok/s
```

`prompt_read` はログの prompt 読み込み時間、`total` はその読み込み時間と decode 時間の和です。`prefill` と `decode` の速度値はエンジン要約行から取得します。時間は出力時に整数ミリ秒へ丸められます。これはサーバー側の表示値で、エンジンログの元行も引き続きログファイルにあります。

エンジンは request 要約を `stderr` に `strata serve: prompt ...` の形で出力します。正規表現はキャンセル時の `N of M read` も許容しているため、その要約行も条件に合えば再掲されます。一方、要約行が正規表現に合わない場合は出力されません。

変数はサーバー起動時だけに固定保存されるのではなく、各 `StrataEngine.__init__` で読みます。engine の再起動は同じインスタンスの `__init__` を再実行します。ただし、ログパスごとに `_echoing` へ一度だけ登録するため follower thread は重複起動しません。いったん thread が起動すると、その thread はログを追い続けるため、実行中に環境変数を削除しても出力は止まりません。起動時に無効で、後から値を設定した場合は、engine の再初期化時にそのログパスの follower がまだなければ開始します。

## 文書との照合

`docs/DETAILS.md` および README 群に `STRATA_REQUEST_LINES` の説明は見つかりませんでした。上記の挙動は、調査対象 HEAD の Python サーバーと C++ engine の実装から確認したものです。性能や生成結果への影響を測定・主張するものではありません。

## 根拠

- `serve/server.py:352-356`: engine 要約行のパターンと抽出フィールド。
- `serve/server.py:408-428`: follower のログ読込、再掲形式、出力の flush。
- `serve/server.py:623-659`: lazy 初期化、ログ有無による条件、環境変数の判定、thread の一度だけの登録。
- `serve/server.py:880-906`: 再起動が `__init__` を再実行すること。
- `serve/server.py:6073-6077,6261-6265`: 通常起動と replica 起動における engine 作成。
- `src/program/generate.cpp:12258-12269`: prompt 読込および decode 完了後に engine が `stderr` へ出す要約と、キャンセル時の部分読込表現。
