# `--check`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` の macOS (Apple Silicon) 経路 |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は Mac の前提条件を確認して終了する |

## 役割

Apple Silicon 用 Metal 経路で、チップが Apple Silicon か、macOS が必要な版か、Command Line Tools があるかを確認し、Mac の情報・空き容量・各問題を表示して終了します。モデルサイズの選択、エンジンの build、モデルの download、server の起動には進みません。通常の `setup.py` は macOS でこの parser に引数を渡します（ただし Control モードや Hy4-Flash / Inkling-2-Mini の経路は別処理です）。`engine/metal/setup_mac.py:372-430`、`terminal/setup.py:9206-9210,11216-11219`。

## 使い方

```sh
# Strata checkout のルートで、Apple Silicon Mac の前提条件を確認
./setup.sh --check
```

## 値と既定値

値を取らない `store_true` フラグで、既定値は `False` です。別名や数値範囲はありません。macOS parser は `parse_known_args` を使うため、同 parser が知らない引数は拒否せず `not used on a Mac: ...` と警告します。`engine/metal/setup_mac.py:397-405`。

## 実行時の動作

`--check` があると、インストール済み Metal 設定があっても server の通常起動を飛ばし、Mac の確認へ進みます。`mac_info()` の情報から問題を集め、すべてを警告として表示した後、data フォルダの空き容量を表示します。問題があれば終了コード `1`、なければ `0` で終了し、モデル選択以降の setup 処理には進みません。`engine/metal/setup_mac.py:416-432`、`terminal/strata_control/mac_fit.py:124-145,155-167`。

この早期終了より前に `data_folder_for(a)` が実行されます。共通処理は data フォルダを作成し、条件次第では既存のモデルデータを移動して設定ファイルを更新します。特に `--data-dir` を指定した場合、`--move-data` や `--yes` との組み合わせ、既存データの有無によって処理が変わります。そのため `--check` はデータフォルダ周りの副作用まで抑止する read-only モードではありません。また空き容量表示の `free_gb()` も対象ディレクトリがなければ作成します。`engine/metal/setup_mac.py:412-414,427-430`、`terminal/setup.py:2699-2701,7335-7359,7367-7425,7429-7432`。

通常の `./setup.sh --check` 単独では `data_folder_for` が既定の data フォルダを解決・作成します。既知でない `--model` / `--family` を併記した場合は、parser より前の feed モデル解決が実行されることがあります。`engine/metal/setup_mac.py:361-370,374`。

## 適用条件と副作用

- 対象は `setup.py` が `sys.platform == "darwin"` で Metal setup に委譲する通常の macOS 経路です。Control モード、Hy4-Flash、Inkling-2-Mini は同じ分岐から除外されています。`terminal/setup.py:9206-9210,11216-11219`。
- 確認項目は Apple Silicon、macOS 15.0 以上、Metal engine を build するための Command Line Tools です。free disk は表示されますが、この `--check` 分岐では閾値と比較して失敗にはしません。`terminal/strata_control/mac_fit.py:15,155-167`、`engine/metal/setup_mac.py:420-430`。
- この分岐自体は build・model download・server 起動を行いません。ただし前述の data フォルダ解決はチェック分岐より前に実行されます。

## 出力とエラー

Mac 情報と空き容量は標準出力に表示され、確認項目の問題は `[!]` 形式の警告として並びます。問題が1つ以上あれば `1`、問題がなければ `0` を返します。フラグ自体の値検証はありません。別の parser が知らない引数については警告を表示して処理を続けます。`terminal/setup.py:997-1005,1039-1047`、`engine/metal/setup_mac.py:403-430`。

## 根拠

- `engine/metal/setup_mac.py:372-405` — macOS parser、`--check` 登録、未知引数の警告、feed 解決の条件。
- `engine/metal/setup_mac.py:416-432` — 既存設定時の起動回避、Mac 検査、空き容量表示、終了コードと後続処理の停止。
- `terminal/setup.py:9206-9210,11216-11219` — 通常の macOS setup から Metal parser への委譲と適用経路。
- `terminal/strata_control/mac_fit.py:124-145,155-167` — 取得する Mac 情報と検査条件。
- `terminal/setup.py:2699-2701,7335-7359,7367-7425,7429-7432` — 空き容量確認のディレクトリ作成、data フォルダの作成・移動・設定保存、および `data_folder_for` からの呼び出し。
