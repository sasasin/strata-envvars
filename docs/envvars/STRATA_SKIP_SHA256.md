# `STRATA_SKIP_SHA256`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。対象は Strata 所有のソースと文書。外部ライブラリ・GPU driver の環境変数動作は対象外。

## 役割

`setup.py` が取得した ready-made engine の ZIP を展開する前に行う、公開済みサイズと SHA-256 の照合を省略するための開発・運用向けフックです。値が文字列として厳密に `1` の場合、Strata は照合を行わず警告を出して次のインストール処理へ進みます。通常の CUDA engine と Windows AMD 用 HIP engine のダウンロード後に共通の検証関数が呼ばれるため、どちらにも適用されます。

## 値と判定

| `os.environ.get()` の結果 | 動作 |
|---|---|
| 未設定（`None`） | 検証を続ける |
| 文字列 `1` | SHA-256 と公開サイズの照合を両方省略し、警告を出して戻る |
| 空文字、`0`、`true`、`01` などその他すべて | 検証を続ける |

数値変換や真偽値変換はせず、Python の文字列との完全一致です。大文字小文字、前後の空白、先頭文字だけの比較もありません。関数呼び出しごとに環境を読み取ります（結果の static cache はありません）。

検証を続ける場合、GitHub release API から asset の公開サイズと `sha256:` digest を取得できれば、まずファイルサイズを照合し、次にファイル全体の SHA-256 を比較します。不一致ではダウンロード済み ZIP と `.done` マークを削除して `UnverifiedEngine` を送出します。公開 digest を取得できない場合（オフライン、rate limit、digest のない release、ローカルフォルダーまたは通常の mirror など）は、変数が未設定でも警告を出して未検証のまま進みます。

## 有効になる条件

- `setup.py` が ready-made engine archive をダウンロードして `verify_engine_archive()` を呼ぶ経路で有効です。通常の engine は `get_prebuilt()`、Windows AMD の prebuilt HIP engine は `get_prebuilt_hip()` がこの関数を呼びます。
- すでに条件を満たす engine がインストール済みでダウンロードが発生しない場合、この変数による検証処理は実行されません。
- 検証を省略しても、その後に行う ZIP 展開、engine の版・backend・GPU 対応の確認、インストール処理は残ります。これらの確認を回避する変数ではありません。
- `setup.py` の別処理にある `verify_sha256()`（モデル shard の照合）ではこの変数を参照しません。

## 実行時の詳細

環境変数は `verify_engine_archive()` の冒頭で読み、`== "1"` なら `STRATA_SKIP_SHA256=1: NOT checking ...` から始まる警告を出して即時 return します。このため、この経路では digest API の問い合わせ、公開サイズ確認、SHA-256 計算のいずれも行いません。値は起動時に一度だけ固定されるのではなく、各 archive 検証呼び出し時に読み取られます。

通常検証で不一致になった場合、初回導入では `engine_refused()` がエラーを出して setup を止めます。更新時は既存 engine を保持し、悪いダウンロードを展開・置換に使わず、警告を出して既存 engine を使える状態にします。`STRATA_SKIP_SHA256=1` の場合、この不一致処理には入りません。

## 文書との照合

`docs/TROUBLESHOOTING.md` は `STRATA_SKIP_SHA256=1` でチェックを省略すると説明しています。現行コードでは SHA-256 のみならず、GitHub が公開する asset サイズの照合も同じ早期 return により省略されます。また、GitHub から digest を取得できないケースは、この変数なしでも警告後にインストールへ進みます。測定値や速度効果は本変数の役割の説明に必要な資料がないため記載しません。

## 根拠

- `setup.py:2798-2836`: `verify_engine_archive()` の対象、厳密な値比較、警告と早期 return、通常検証への分岐。
- `setup.py:2837-2859`: digest を得られない場合の警告・継続、公開サイズと SHA-256 の検査、不一致時の削除・例外。
- `setup.py:2481-2487`: Windows AMD prebuilt HIP archive のダウンロード後に共通検証関数を呼び、不一致を扱う箇所。
- `setup.py:3005-3012,3015-3043`: ready-made engine のダウンロード、検証後の展開・版/GPU 対応確認・導入。
- `setup.py:2862-2876`: 初回導入と更新時で検証拒否時の扱いが異なる箇所。
- `setup.py:1626-1648,5499-5502`: モデル shard 用の別の `verify_sha256()` 経路。本変数の参照はない。
- `docs/TROUBLESHOOTING.md:69-70`: 利用者向け説明。
