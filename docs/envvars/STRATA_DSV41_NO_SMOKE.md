# `STRATA_DSV41_NO_SMOKE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

## 役割

DeepSeek V4.1 のセットアップ中に行う、16 token の短い smoke test を省略するためのセットアップ用環境変数です。モデルの実行時設定ではありません。値が有効でもモデルファイルの取得・pack 作成・pack 内容の検査は省略せず、最後の回答テストだけをスキップします。

## 値と判定

`setup.py` は `os.environ.get("STRATA_DSV41_NO_SMOKE") == "1"` を文字列全体で比較します。数値変換、trim、大文字小文字変換はしません。

| 環境値 | 判定 | 結果 |
|---|---|---|
| 未設定 | `None == "1"` は偽 | smoke test を実行 |
| 空文字 | `"" == "1"` は偽 | smoke test を実行 |
| 完全一致の `1` | 真 | smoke test を省略し、警告を表示 |
| その他（例: `0`, `true`, ` 1`, `1 `, `01`） | 偽 | smoke test を実行 |

この判定を上書きする CLI 引数や、別の環境変数による優先順位はありません。

## 有効になる条件

- 通常の `install_dsv41()` 経路で、選択モデルの recipe が `ista` または `udlow` であること。このとき `ista` が真になり、pack の検査後に環境変数が評価されます。
- `STRATA_DSV41_NO_SMOKE=1` の場合、pack 検査に成功した後に限り smoke test 呼び出しを省略します。pack 作成や `--pack-info` 検査の失敗を回避するスイッチではありません。
- 他 recipe では `ista` が偽のため、この環境変数の判定箇所へ進まず、ここで定義された smoke test も実行されません。
- macOS の Control モードで選ばれる `mac_dsv41_setup()` も `install_dsv41()` を呼びますが、同関数内の `ista` / `STRATA_DSV41_NO_SMOKE` 分岐は共通です。一方、通常の macOS 非 Control セットアップは `mac_setup()` に分岐するため、この `main.py` 相当の読み取り箇所には到達しません。Intel SYCL 専用セットアップも別経路です。

## 実行時の詳細

変数は `install_dsv41()` の pack 準備・完全性検査後、smoke test の直前に評価されます（`setup.py` のその時点の `os.environ` を読みます）。結果を保存する static cache はなく、セットアップを別途起動し直せばそのプロセスの環境値で判定します。CLI 引数から値を設定する処理もありません。

値が `"1"` のときは stdout に `  [!]  the 16-word test run was skipped (STRATA_DSV41_NO_SMOKE=1)` を出して、その先の処理へ進みます。省略しない場合は `tools/dsv41/smoke.py` を Python 子プロセスとして起動し、固定質問に対する16 token の応答を検査します。子プロセス起動時の OS error または timeout、非0終了は smoke 失敗となり、セットアップはエラーを表示して終了コード 1 で停止します。スイッチを有効にするとこの smoke に由来する失敗経路はなくなりますが、事前の pack 検査や後続処理の失敗は別です。

`docs/DEEPSEEK41.md` はセットアップが pack を検査して16-tokenの質問テストを行う手順を記しています。環境変数による省略条件の記載は確認できず、上記の条件は調査対象 commit のコードを根拠にしています。

## 根拠

- `setup.py:8523-8530` — 選択モデル recipe から `ista` を定める条件。
- `setup.py:8697-8716` — pack を作成し、`ista` 経路で pack の完全性を検査。
- `setup.py:8717-8726` — 変数の完全一致判定、スキップ警告、smoke 実行と失敗時の `fail()`。
- `setup.py:8410-8423` — smoke 子プロセスの起動、timeout / 起動失敗の処理、終了コードによる成否判定。
- `setup.py:887-909` — `say()` は flush 付き標準出力、`warn()` は `[!]` 表示、`fail()` はセットアップ停止と `sys.exit(1)`。
- `setup.py:9038-9059, 9062-9069, 9220-9225` — macOS Control、通常 macOS、SYCL のセットアップ経路。
- `docs/DEEPSEEK41.md:73-78` — pack・smoke の説明（この文書には対象変数の説明なし）。

候補一覧 `000_envvers.md` にはこの名前があります。Strata の全参照検索では実際の値読み取りは `setup.py:8717` の1箇所で、直接の Python 環境参照です。helper 経由・動的な名前渡し・他の読み取り箇所は見つかりませんでした。
