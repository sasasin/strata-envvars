# `TUNE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Docker イメージの通常起動で、`strata launch --no-tui` にチューニングモードを渡す。`quick` または `thorough` は launch 中にモデル用のチューナーを実行し、`skip` は実行しない。Strata CLI 自体に `TUNE` の読み取り箇所はなく、Docker entrypoint を通さず `strata launch` を直接起動した場合、この環境変数は CLI の選択に影響しない。entrypoint は値を CLI 引数 `--tune` へ変換する。`tools/docker/entrypoint.sh:184-185,253-266`、`terminal/strata_cli/launch/cmd.py:121`。

## 値と判定

entrypoint は `${TUNE:-}` で未設定・空文字を空にし、`tr 'A-Z' 'a-z'` で ASCII の大文字を小文字化する。空か `skip` なら `--tune` を付けない。それ以外の値は `--tune <値>` に渡され、CLI の `_choice` が前後空白を除いて小文字化し、`quick`・`thorough`・`skip` のいずれかと完全一致するか検査する。数値への変換や値域 clamp はない。`tools/docker/entrypoint.sh:254-266`、`terminal/strata_cli/launch/cmd.py:35-43,121`、`terminal/strata_cli/launch/settings.py:29,141`。

| 起動経路・条件 | unset / 空文字 | 有効になる値（例） | 無効・または実質無効な値（例） |
|---|---|---|---|
| Docker Compose の NVIDIA / AMD / Intel 定義 | `${TUNE:-skip}` により `skip` をコンテナへ設定 | `quick`, `thorough`。大文字小文字は entrypoint で小文字化 | `skip` はチューニングしない。Compose 補間で空値も既定値 `skip` になる |
| entrypoint を使う Docker 起動（Compose 以外） | `--tune` を渡さず、CLI の既定 `skip` | `quick`, `thorough`。例: `QUICK` も `quick` として渡る | `skip` は引数なしと同じ。その他は CLI の選択肢検査で拒否 |
| 既に調整済み preset があり、`RETUNE` が `1` でない | ― | 値が `quick` / `thorough` でも再測定せず既存設定を保持 | この経路では値を `--tune` に渡さないため、不正な非空値も検査されず無視される |

entrypoint の正規化では前後空白を除去しないが、CLI の `_choice` が引数の前後空白を除去するため、例えば `" QUICK "` も受理される。空白を含む値は CLI に渡った後に判定される。CLI の他の値（例 `true`、`0`、`1`）は選択肢ではなく、`argument --tune: '値' is not a tuning mode. Choose one of: quick, thorough, skip.` の形式で拒否される。未調整 preset で不正値を渡すと launch プロセスは引数エラーで終了し、entrypoint は非 0 の戻り値をコンテナ終了として報告する。`terminal/strata_cli/launch/cmd.py:35-43`、`tools/docker/entrypoint.sh:254-264,303-316`。

## 有効になる条件

- Docker の既定 entrypoint 起動であること。entrypoint は任意の別コマンド（`strata ...` を含む）を受け取ると起動処理を切り替えるため、その経路では TUNE を CLI に渡さない。`tools/docker/entrypoint.sh:68-70`。
- 値が空でも `skip` でもないこと。さらに `RETUNE=1` でない場合、entrypoint が preset 一覧から調整済みと判定した既存 preset では再測定しない。`RETUNE=1` のときは `--retune` も追加する。`tools/docker/entrypoint.sh:253-263`。
- launch にチューナーへ渡せるモデル・実行条件があること。`Runner.tune()` は `skip`、および Qwen tuning knobs を持たない native Strata family の Hy4-Flash / Inkling-2-Mini では直ちに戻る。既存 tuning preset、標準設定が既に最速だった記録、同じモデルと選択内容の保存済み tuning があれば、`--retune` なしでは再測定を省く。`terminal/strata_cli/launch/runner.py:2372-2395`。
- launch が engine 問題でチューニング段階より前に終了しないこと。runner は engine 問題を検出すると結果を返し、その後の `self.tune()` へ進まない。`terminal/strata_cli/launch/runner.py:3328-3337`。

Docker Compose の3 backend 定義はいずれも未設定時に `skip` を注入する。entrypoint が起動する `launch --no-tui` の設定では、`--tune` が生成された場合に preset 由来の設定へ反映される。`tools/docker/compose/docker-compose.nvidia.yml:16-24`、`tools/docker/compose/docker-compose.amd.yml:15-23`、`tools/docker/compose/docker-compose.intel.yml:15-23`、`terminal/strata_cli/launch/cmd.py:274-277`。

## 実行時の詳細

TUNE は Docker コンテナの entrypoint 実行時に一度シェルで読み取られる。プロセス起動後に環境変数を変更しても、その起動で組み立て済みの引数は変わらない。CLI 側の `LaunchSettings` の既定値も `skip`。`quick` / `thorough` のとき、runner はそれぞれ同名の `--mode` を付けた `strata tune auto <profile>` 子プロセスを起動する。測定状態ファイルを1秒間隔で読み、進捗を出し、完了時の結果を preset に記録した後にモデルを開始する。`skip` はチューナー起動を行わない。`tools/docker/entrypoint.sh:254-266,303-310`、`terminal/strata_cli/launch/settings.py:141`、`terminal/strata_cli/launch/runner.py:2372-2407,2411-2439,3323-3342`。

実行されるのは引数どおり `quick` または `thorough` の tuning mode で、Docker entrypoint は別環境変数 `TUNE_ALLOW_SMALL=1` の場合に限り `--tune-allow-small` も追加する。再測定を許可する `RETUNE=1` は `TUNE` が空または `skip` のとき entrypoint から作用せず、チューニング値が有効な分岐でのみ `--retune` になる。`tools/docker/entrypoint.sh:253-266`、`terminal/strata_cli/launch/cmd.py:121-122,143-145`。

## ログと測定値

entrypoint はチューニング引数を付けると `Tuning is on (TUNE=<小文字化した値>): the first start takes longer (up to about 20 minutes, once).`（`quick`）または上限表示が `about 120 minutes`（`thorough`）のログを出す。測定を飛ばす既存 preset では `This preset is already tuned; keeping the tuned settings (set RETUNE=1 to tune again).` を出す。runner は測定を始めると `Tuning for the best speed. Close other heavy programs while it measures.` を通知し、完了時に `Tuning result: ...` を通知する。これらは実装上の案内・進捗文言であり、測定時間の保証ではない。`tools/docker/entrypoint.sh:258-263`、`terminal/strata_cli/launch/runner.py:2381-2393,2405-2421,2431-2439`。

## 根拠

- `tools/docker/entrypoint.sh:68-70,184-185,253-266,303-316`
- `tools/docker/compose/docker-compose.nvidia.yml:16-24`
- `tools/docker/compose/docker-compose.amd.yml:15-23`
- `tools/docker/compose/docker-compose.intel.yml:15-23`
- `terminal/strata_cli/launch/cmd.py:35-43,121-122,143-145,274-277`
- `terminal/strata_cli/launch/settings.py:29,141-142`
- `terminal/strata_cli/launch/runner.py:2372-2439,3328-3342`
