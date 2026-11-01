# `STRATA_REPLICA_PROFILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main`（変更なし）。

## 役割

`setup.py` が複数 GPU の構成を作るとき、通常の layer split に代えて、GPU ごとに独立した engine を起動する replica serving profile を要求します。セットアップは対象構成に限って `gpu`、`replicas`、共有 expert arena、batch 用環境設定、必要なら `parallel` を run config に書きます。リクエストを各 replica に振り分ける処理はサーバー側の既存機能です。この環境変数自体を読むのはセットアップ処理であり、engine や server の実行時設定ではありません。

## 値と判定

セットアップの入口はまず `os.environ.get("STRATA_REPLICA_PROFILE")` の真偽値を調べます。値が空でなければ profile 判定 helper を呼びます。helper は環境値を `str(...)` にし、前後空白を除去して小文字化した後、`1`, `on`, `yes`, `true` のいずれかと完全一致する場合だけ要求ありとします（大文字小文字は区別しません）。

| 環境値 | helper の判定 | セットアップ上の扱い |
|---|---|---|
| 未設定 | false | CLI 指定がなければ helper を呼ばず、profile を要求しない |
| 空文字 | false | CLI 指定がなければ入口の真偽値判定で helper を呼ばない |
| `1`, `on`, `yes`, `true`（大小文字不問、前後空白可） | true | 適用条件を検査する |
| `0`, `off`, `no`, `false`、その他の文字列 | false | 適用しない。無効値エラーにはせず、通常は何も表示しない |

数値変換や先頭文字判定はありません。たとえば `2`, `01`, `true extra` は false です。`setup.py --replica-profile` は環境値とは別の要求経路で、helper 呼び出し前に config の `replica_profile` を `True` にします。そのため CLI 指定は環境値が明示的な false でも優先します。helper 単体では config の `replica_profile` が `None` 以外なら環境値より先に判定し、値が Python の `True` そのものの場合だけ true です。ただし Strata 内でこの helper を適用する本番呼び出し元は `setup.py` のみで、その config は CLI 指定時にだけこのキーを設定します。

## 有効になる条件

要求が true でも、`setup.py` が複数 GPU を layer split として扱う経路でのみ適用判定に進みます。さらに以下をすべて満たす必要があります。

- CLI の `--replicas` が指定されていない。helper 自体も渡された config に既存 `replicas` があれば拒否しますが、この `setup.py` の呼び出しは既存 run config の引き継ぎより前で、新規 config に対して行われます。従って、過去の run config に `replicas` が保存されているだけでは、この時点の拒否条件になりません。profile を生成しなかった場合、過去の `replicas` は後段の config 引き継ぎで保持されます。
- layer split が `auto`（または未指定）で、engine 引数に `--layer-split` がない。
- config に既に `replicas` がなく、`arch` が `deepseek41` ではなく、engine 引数に `--peer-device` がない。
- GPU が 2 枚以上あり、選択された各 GPU の VRAM が 24 GB 以上。
- model name と engine 引数を小文字化・記号正規化した文字列に `qwen3_8` と、`iq3_s`, `iq3_xxs`, `q2_0` のいずれかが含まれる。
- RAM から見積もる replica 数が 2 以上。

RAM 見積りは `iq3_s` で expert arena 50.3 GB、`iq3_xxs` 42.9 GB、`q2_0` 34.0 GB として行います。Linux では共有 arena 1つ分と OS/server 用 12 GB を除いた残りを replica あたり 8 GB で割り、Windows など共有不可の platform では arena と 8 GB の合計を replica ごとに見積もります。採用数は GPU 枚数を上限とします。条件不足時は「needs two or more GPUs」「measured only for ...」「a card has under 24 GB ...」「... GB of RAM; two engines need about ...」などの理由を `setup.py` が表示し、profile を適用しません。

優先順位には setup のタイミング上の注意があります。既存 run config の `replicas` や、後から引き継がれる手編集 engine args は、profile 判定後に `write_setup_config()` が carry over します。従ってこの環境変数が有効な setup 実行では、過去 config の `replicas` は helper の拒否条件としては見えず、profile の新しい `replicas` が作られた場合には引き継ぎで置き換わりません。`--replicas` など今回の CLI と、profile 判定時点で生成済みの args/config が判定条件です。

適用時に利用者の指定を尊重する条件もあります。CLI の `--replicas`、peer device、別 model family、明示 layer split は profile を止めます。`--parallel N` が指定されている場合、または config args に `--batch` / `--slots` がある場合、profile は推奨 `parallel` を追加しません。スイッチ用環境変数がプロセス環境に既に存在する場合も、profile はそのキーを config に追加しません。config の既存 env 値も `setdefault` により保たれます。

## 実行時の詳細

判定は `setup.py` の run config 作成中に行われ、リクエストごとの再評価や cache はありません。`STRATA_REPLICA_PROFILE` の値を run config の `env` に転送するコードもありません。全リポジトリで名前を検索した結果、環境値を読む箇所は `setup.py` と `strata_control/replica_profile.py` のみです。server が別途読むのは共有 arena 用の `STRATA_REPLICA_SHARED_ARENA` であり、この変数ではありません。

適用されると、RAM が許す先頭の GPU を `cfg["gpu"]` に設定し、GPU ごとに 1 枚を使う `cfg["replicas"]` を作ります。Linux/Windows では `replica_shared_arena: true` を既定設定します。また、次のキーについて、親プロセス環境に存在しないキーを config env に既定値として追加します: `STRATA_QSA_SLOTS=1`, `STRATA_BATCH_SELF_COMMIT=1`, `STRATA_SLOT_COPY_DIRECT=1`, `STRATA_CKPT_POOL=1`, `STRATA_CKPT_POOL_READY=4`, `STRATA_SLOT_CKPT_MOVE=1`, `STRATA_SLOT_COPY_BATCHSYNC=1`。`parallel` の指定がなければ replica 数が 2 のとき 8、それ以外は 4 を config に設定します。

サーバーは run config の replica groups を使って各 engine を起動し、前段の `ReplicaEngine` がリクエストを分散します。profile が要求されても適用条件を満たさない場合、setup は理由を表示して続行します。profile 適用中に例外が起きた場合も `  (the replica profile was not applied: {e})` を表示し、セットアップを止めません。適用時の表示には「`N engines of one card each instead of one layer split ...`」や共有 arena の有無、必要に応じて RAM によって除外した GPU 数が含まれます。

## 根拠

- `setup.py:9199-9203` は `--replica-profile` CLI option を定義。
- `setup.py:10338-10362` は複数 GPU の layer split 経路での環境値 truthiness gate、helper 呼び出し、CLI config 設定、結果表示、例外時の継続を実装。
- `strata_control/replica_profile.py:39-48` は許可値と config/environment の判定順を実装。
- `strata_control/replica_profile.py:76-98` は要求、既存指定、GPU 数、model/quant、VRAM、RAM の適用条件と理由を実装。
- `strata_control/replica_profile.py:30-38,101-130` は arena/RAM 定数、switches、GPU ごとの replica config、`parallel` 推奨を実装。
- `setup.py:6513-6543,6648-6683` は setup が書かない既存 config key と手編集 args の引き継ぎ、および生成 config の保存を実装。
- `serve/server.py:8688-8696` は replica engine 群の起動ログと server 前段での request routing を説明。
- `serve/replicas.py:55-84,161-180` は config の replica group 解釈と共有 arena の別設定を実装。`serve/replicas.py:204-210` での `replica_profile` import は RAM 警告見積り用定数の参照であり、対象環境変数の読み取りではありません。
- `docs/BATCHING.md` と `docs/DETAILS.md` には、この環境変数の実行時判定や適用条件の説明は見つかりませんでした。挙動の根拠は上記ソースです。
