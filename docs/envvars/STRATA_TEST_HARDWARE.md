# `STRATA_TEST_HARDWARE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

Strata Host のハードウェア検出で、ホスト固有のメモリ容量・空きメモリ・GPU 検出結果を JSON から与え、実機 probe の一部を置き換えるテスト用 override です。実装コメントも tests only としています。ただし読み取り側に `NODE_ENV` やテストプロセスの判定はなく、Host サーバーを通常起動した場合もこの変数が設定されていれば適用されます。Strata の本体エンジン（C++/CUDA 等）の設定ではありません。

## 値と判定

`apps/host/server/hardware.mjs` の `testHardware()` は `process.env.STRATA_TEST_HARDWARE` を読みます。

| 値 | 結果 |
|---|---|
| 未設定、空文字 | falsy のため override なし。実機 probe を使う |
| 空白だけ、壊れた JSON | `JSON.parse` が失敗し `null`。エラーを表示せず実機 probe に戻る |
| JSON の `null`、数値、文字列、真偽値 | parse 後の値が truthy な object ではないため override なし |
| JSON object | override として採用。各プロパティを下記の nullish fallback で使用 |
| JSON array | JavaScript では `typeof value === 'object'` かつ truthy のため採用されるが、通常プロパティを持たない array では各値が fallback する |

期待される形は `{"totalGb":128,"freeGb":100,"gpus":[...]}` です。ただし object の各フィールドに対する型・範囲・GPU 要素の検証はありません。`totalGb`、`freeGb`、`gpus` はそれぞれ `??` で選ばれるため、キー省略または JSON `null` は実機値に fallback します。0 は有効な指定値です。GPU probe を抑止するには `gpus: []` を指定します。`gpus` に配列以外を指定するなど期待形に合わない値では、後続処理が失敗する可能性があります。

## 有効になる条件

- `apps/host/server/index.mjs` が Host サーバーとして起動し、ハードウェア検出を呼び出すこと。OS、GPU backend、build macro、CLI 引数、モデル状態による有効化条件はありません。
- 各項目は個別に上書きされます。`totalGb` がなければ `os.totalmem()`、`freeGb` がなければ Linux/macOS の空きメモリ probe または `os.freemem()`、`gpus` がなければ OS ごとの GPU probe を使います。CPU 情報、ホスト名、platform、arch、アプリ版、disk 情報はこの変数では置き換えず、通常の検出を続けます。
- `totalGb` と `freeGb` はメモリ表示、使用量・pressure、メモリ check とモデル推奨の計算へ影響します。`gpus` は GPU 一覧と accelerator 選択へ影響し、空配列なら CPU-only 判定になります。Apple silicon で `gpus` を省略した場合、上書きされた `totalGb` は fallback で推定する GPU メモリ容量にも使われます。
- CLI や別環境変数との優先順位による競合はありません。通常 probe との関係は上記のフィールド単位の nullish fallback です。

## 実行時の詳細

サーバー起動時に `hardware.detect({ force: true })` が呼ばれ、その結果が boot hardware としてログ表示や monitor 初期化に使われます。`detect()` は cache が有効なら通常は最大30秒その結果を返し、再検出時に `testHardware()` を実行します。`/api/hardware` は通常 cache を使い、`?reprobe=1` では強制再検出します。モデル読み込みや保存領域変更などからも検出関数が呼ばれます。環境値は各検出時に `process.env` から読み直されるため、プロセス内で変更された場合は cache が失効した後か強制再検出時に反映されます。`cachedHardware()` は直近の検出結果を返すだけです。

採用された値は `hw.memory`、`hw.gpus`、`hw.accelerator` などに組み立てられ、互換性 check、verdict、推奨 variant に続きます。たとえば `totalGb < 16` はメモリ check を fail にし、`gpus: []` は「No GPU accelerator found — Strata will run on the CPU」という check detail を作ります。起動ログには `hardware · <accelerator> / <backend> / <cores> cores / <memory> GB` が出て、`GET /api/hardware` は検出結果を JSON で返します。

JSON parse 失敗時に専用の警告やエラーはありません。壊れた値でも override が無視され、通常検出へ進みます。構文として有効でもフィールドの型が不正な値は事前検証されず、通常 probe を誤って置き換えたり後続計算で異常値・例外を生じたりし得ます。ログや API 以外の終了・失敗動作について、Strata はこの変数専用の経路を実装していません。

## 根拠

- `apps/host/server/hardware.mjs:17-40` — hardware cache と `testHardware()`。未設定・空文字・parse 失敗・object 判定。
- `apps/host/server/hardware.mjs:42-95` — 30秒 cache、force 条件、環境値の適用、検出結果の cache。
- `apps/host/server/hardware.mjs:47-56,58-94` — tests-only コメント、メモリ/GPU の個別 fallback と hardware object の構築。
- `apps/host/server/hardware.mjs:203-220,223-297,304-318` — GPU/CPU accelerator 選択、メモリ判定、verdict、推奨 variant。
- `apps/host/server/index.mjs:235-245,278-282` — 起動時の強制検出、初期化、hardware ログ。
- `apps/host/server/index.mjs:1396-1402` — `/api/hardware` と `reprobe=1`。
- `apps/host/server/index.mjs:1446-1451,1493-1517` — 保存先変更時とモデル読み込み時の検出利用。
- `apps/host/server/engine.mjs:69-83,195-219,230-243` — engine config、restart、validation での hardware 利用。
- `apps/host/server/monitor.mjs:296-312` — monitor のハードウェア値への反映。
- `apps/host/tests/no-model-chat.test.mjs:51`、`apps/host/tests/runtime-api.test.mjs:16` ほか — Host の統合テストが子プロセスへこの変数を渡している箇所。テストの使用例であり、値の受け入れ範囲の独立した仕様根拠ではありません。

`docs/DETAILS.md` にこの変数の仕様や測定値は見つかりませんでした。上記は調査対象 commit の実装から確認できる範囲です。
