# `STRATA_DF2_RING_LOG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DFlash2 ドラフターが各 context 更新から activation の量子化行をホスト側の lineage log に保存する機能を切り替えます。ログがあると、会話の再開・巻き戻し・別会話への切り替えでリングの必要行が上書き済みでも、保存した行からリングを再構築できます。無効時は従来の動作となり、再開位置に必要な行がリングに残っていなければリングを新しい epoch にします。

この設定が参照されるのは `STRATA_HAVE_DFLASH2` 付きで組み込まれる DFlash2 実装です。`generate` で DFlash2 を使うには `--draft dflash2` と draft pack などの起動条件を満たす必要があります。コードにこの環境変数を設定する CLI 引数はありません。主な復元効果は `serve` の継続リクエストで現れます。

## 値と判定

実装は値全体を parse せず、環境変数が設定されていて先頭文字が `'0'` かだけを見ます。

| 環境値 | リングログ |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効。先頭は NUL であり `'0'` ではない |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| その他（例: `1`, `10`, `true`, `false`, ` 0`） | 有効 |

数値変換、空白除去、大文字小文字の判定はありません。したがって `false` も有効で、`0anything` は無効です。CLI 引数や別の設定ファイルによる上書き経路は、この設定の読み取り実装にはありません。

関連する `STRATA_DF2_LOG_MIB` は、リングログが有効な場合に lineage stash の容量を MiB 単位で指定します。リングログを先頭 `0` で無効にした CUDA/HIP 経路では、この stash 容量設定も読みません。

## 有効になる条件

- DFlash2 がビルドに含まれ、DFlash2 drafter が実際にロード・割り当てされる必要があります。`generate.cpp` は `STRATA_HAVE_DFLASH2` の下で `o.draft == "dflash2"` を処理し、pack などの要件を満たすと `df2.load()` を呼びます。条件を満たさない場合は DFlash2 を起動せず、通常は MTP drafter に fallback します。
- CUDA/HIP 実装では `alloc()` が pinned host staging を確保した後に設定を読みます。SYCL 実装も `alloc()` 中、device buffer 割り当て後に設定を読みます。
- 設定が未設定または先頭が `0` 以外でも、ログ用 staging の割り当てに失敗するとログは無効になります。機能自体の起動失敗にはせず、stderr に警告を出して従来のリング動作に戻ります。

## 実行時の詳細

設定は各 drafter の allocation 時に読み、結果を `log_on_` に保持します。通常の drafter は `load()` から `alloc()` に進みます。CUDA/HIP の batch slot drafter も `clone_alloc()` から `alloc()` に進むため、各 slot の割り当て時にも環境を読みます。既存 drafter は allocation 後に環境値を変更しても再評価しません。

ログが有効なら、context 更新や draft 更新で書き込む量子化 activation codes と block scales を host staging に移し、同期後に lineage のログへ格納します。`begin_request()` は resume 位置より先に必要な窓の行を確認し、リングにないがログにある行を再構築します。ログにない行は欠損として数え、再構築 scratch の確保など再構築自体が失敗した場合は stderr に理由を出し、その request ではリングを開始し直します。ログ無効時は過去の lineage を stash から復元せず、resume prefix とリングの整合性が崩れていればリングを開始し直します。

ログ staging 確保に失敗した場合の実装ログは、CUDA/HIP では `strata dflash2: the ring log's staging does not fit in pinned memory: the log is off`、SYCL では `strata dflash2: the ring log's staging does not fit in host memory: the log is off` です。ログ有効時、`serve` が再開要求で行を再構築すると `strata serve: DFlash2: ... context rows of the window rebuilt from the drafter's log ...` を stderr に出します。`STRATA_DF2_RING_LOG` 自体の値を報告するログや、値が無効なことによる終了経路はありません。

## 根拠

- `src/core/dflash2.cpp:245-285,582-591,746-759`: CUDA/HIP 系の allocation、slot clone 経路、先頭文字判定、既定動作と pinned staging 失敗時の警告。
- `include/strata/core/dflash2.hpp:94-120,240-267`: 機能の目的、リング復元の説明、初期値と helper 宣言。
- `sycl/src/core/dflash2.cpp:167-232`: SYCL の先頭文字判定、既定有効、host staging 確保と失敗時の警告。
- `sycl/include/strata/core/dflash2.hpp:44-63,161-177`: SYCL 実装の機能説明と状態。
- `src/core/dflash2.cpp:795-813,815-875,878-959,968-1010,1039-1058`: 行の記録・再構築、再開時のログ参照、ログ無効時の従来経路、context/draft 更新との接続。
- `sycl/src/core/dflash2.cpp:538-611,613-692,714-759`: SYCL の行記録・再構築・再開・更新経路。
- `src/program/generate.cpp:6765-6774,6811-6818,6820-6831,16032-16042`: DFlash2 の起動条件、fallback、batch slot の作成、serve 継続要求での `begin_request()` と再構築ログ。
