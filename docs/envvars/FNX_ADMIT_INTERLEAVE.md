# `FNX_ADMIT_INTERLEAVE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数動作は含めない。

## 役割

`strata-split` の sFNX サーバーで、バッチ要求の admission（prompt の読み込みと最初の token の生成）が終わるたびに、すでに decode 中の slot に decode window を 1 回実行させる設定です。既定では無効です。値を有効にしても、通常の `strata` エンジンや sFNX の単独要求 `GEN` / `GENI` ではこの分岐は実行されません。

## 値と判定

読み取りは `fnx::env_int("FNX_ADMIT_INTERLEAVE", 0)` で行い、戻り値が `0` かどうかで判定します。

| 環境値 | 判定 |
| --- | --- |
| 未設定 | 既定値 `0`。無効 |
| `0`, `+0`, `-0` | 無効 |
| `1`, `-1`, その他の 0 以外の有効な整数 | 有効 |
| 空文字、空白を含む値、数字以外を含む値、整数範囲外 | 整数として不正。例外になり、サーバー起動失敗 |

値は省略可能な符号と十進数字からなる整数として全体を解析します。前後の空白や末尾の文字は許容されず、桁あふれも不正です。値の範囲制限や clamp はありません。CLI 引数や他の環境変数による上書きはありません。根拠: `src/split/src/env.hpp:15-21,33-40`; 読み取りと非ゼロ判定: `src/split/tools/sfnx.cpp:1004`。

## 有効になる条件

- `strata-split` がビルドされ、その sFNX サーバー実行ファイルが使われること。ビルドは `STRATA_BUILD_SPLIT` で opt-in され、CMake は Linux CUDA または HIP の構成に限って split target を作ります (`CMakeLists.txt:2945-2947`; `src/split/CMakeLists.txt:1-7,20-27,92-98`)。
- `sfnx` が `BGEN` または `BGENI` 要求を処理すること (`src/split/tools/sfnx.cpp:973-983`)。`--batch` が 2 未満なら要求は `ERR ... sfnx runs without --batch` となり、interleave 判定箇所へは進みません。
- admission 処理の後に、decode 中または一時停止中の slot が少なくとも 1 つ残っていること (`src/split/tools/sfnx.cpp:459-463,997-1002`)。

`GEN` / `GENI` はこの設定による admission 後の window を呼びません。prompt 読み込み中に進捗 callback から既存 slot の window を実行する経路は別にあり (`src/split/tools/sfnx.cpp:723-737`)、この環境変数の値で制御されません。

## 実行時の詳細

`Server` の `interleave_` メンバー初期化時に一度値を読み、真偽値として保持します。`main` はモデルと engine の構築後に `Server` を作るため、その時点で値が固定されます。プロセス中に環境を変更しても再読込されません (`src/split/tools/sfnx.cpp:1004,1040-1065`)。

要求ループは `BGEN` / `BGENI` を `admit()` に渡し、その処理から戻った後、`interleave_` が有効で slot が動作中なら `decode_step()` を 1 回呼びます。この処理は残っている decode slot を集めて次の window を進めます。要求の admission が成功したかどうか自体は条件に含まれず、`admit()` が戻った後の slot 状態で判定します (`src/split/tools/sfnx.cpp:572-589,857-923,997-1002`)。

具体的な挙動として、既存の slot は、次の batch 要求を読み終えてから次の要求へ進む前に 1 window 進みます。ソースコメントは、複数要求が同時に始まると、後続要求を読んでいる間に先行 slot が decode できる狙いと、要求読み込みに 0.2–0.5 秒かかる例を記しています (`src/split/tools/sfnx.cpp:999-1001`)。この時間はコードコメント上の記述であり、本調査で再測定した値ではありません。

不正値では helper が `FNX_ADMIT_INTERLEAVE: '<値>' is not a whole number` 形式の例外を投げます。`Server` 構築時の例外は `fail()` に渡され、stdout に `ERR ...`、stderr に `sfnx: failed: ...` を出して終了コード 1 で終了します (`src/split/src/env.hpp:34-39`; `src/split/tools/sfnx.cpp:1027-1035,1055-1065`)。この変数専用の有効化・無効化ログはありません。

## 根拠

- 環境整数の変換規則: `src/split/src/env.hpp:15-21,33-40`。
- 変数の一度限りの読み取り、既定値、batch 条件と window 呼び出し: `src/split/tools/sfnx.cpp:999-1004`。
- active slot の定義と window 対象: `src/split/tools/sfnx.cpp:459-463,572-589`。
- 起動時の生成・例外処理: `src/split/tools/sfnx.cpp:1027-1035,1040-1065`。
- split executable のビルド条件: `CMakeLists.txt:2945-2947`; `src/split/CMakeLists.txt:20-27,64-79,92-104`。
- 関連資料 `docs/SPLIT_ENGINE.md` は split engine の概要・起動条件を扱いますが、この変数の動作や測定値は説明していません。コードコメントが参照する `RESULTS-HIP.md` はこの checkout では見つからなかったため、コメント中の「4 x R9700 で no gain」という測定評価は独立に確認できていません。
