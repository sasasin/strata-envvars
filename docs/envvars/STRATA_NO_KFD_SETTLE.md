# `STRATA_NO_KFD_SETTLE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux の HIP エンジンが起動時に行う KFD eviction counter の安定待ちを無効にする診断用スイッチです。通常は対象 GPU で、プロセス自身の eviction counter が 2 秒間変化しなくなるまで待ちます（上限 10 秒）。この変数が有効なら待ちを飛ばし、エンジンは後続の初期化へ進みます。これは待ちだけを制御し、KFD counter の読み取り・GPU 動作そのものは変更しません。`include/strata/core/kfd_settle.hpp:136-149`。

エンジン側で対象クラスを判定してフラグを立てるのは `src/program/generate.cpp:4074-4088, 4118-4123`。条件は全可視 GPU が同一アーキテクチャの統合 GPU であることと、`gfx1103`・`gfx1150`・`gfx1151` のいずれかであることです。アーキテクチャ判定は `src/core/arch_defaults.cpp:151-159`、`include/strata/core/arch_defaults.hpp:68-71` にあります。

## 値と判定

`std::getenv` で値を取得し、未設定ではなく、かつ先頭文字が NUL でも `'0'` でもない場合に settle を早期 return します。文字列全体の比較や boolean / 数値変換はしません。したがって `0` で始まる値（`0`, `0anything`, `01` など）は無効化せず、他の先頭文字なら無効化します。空白は trim されず、先頭が空白なら無効化します。大文字小文字は判定されません。`include/strata/core/kfd_settle.hpp:140-142`。

| 条件 | unset | settle を無効化する値 | 無効化しない値 |
|---|---|---|---|
| Linux HIP、対象 GPU クラス | settle を実行 | 空文字以外で先頭が `0` 以外（例: `1`, `true`, `false`, ` 0`, `-1`） | 未設定、空文字、先頭が `0`（例: `0`, `0anything`, `01`, `0.1`） |
| 非 Linux または対象 GPU クラス外 | settle 呼び出しは実質 no-op | 同上の値でも影響なし | 同上の値でも影響なし |

`getenv` の戻り値が null なら待ちは許可され、明示的な空文字も許可されます。無効な文字列というエラー状態はありません。CLI 引数や別設定への fallback / 優先順位はなく、コード上この変数を読むのは上記の直接読み取りだけです。`include/strata/core/kfd_settle.hpp:140-142`。

## 有効になる条件

- エンジンが `STRATA_USE_HIP` でビルドされ、Linux 上で動作すること。counter を読む本体は `__linux__` の条件付きで、HIP の GPU 初期化・ロード順処理も `STRATA_USE_HIP && __linux__` で囲まれています。`include/strata/core/kfd_settle.hpp:28-32, 138-149`; `src/program/generate.cpp:4074, 4124-4126, 9062-9067`。
- GPU プロパティを取得でき、可視 GPU がすべて統合型かつ同じアーキテクチャで、アーキテクチャが `gfx1103`、`gfx1150`、`gfx1151` のいずれかであること。異なる種類・世代のカードが混在する場合は `all_igpu` が false になり、この settle の既定フラグは立ちません。`src/program/generate.cpp:4077-4088, 4121-4123`; `src/core/arch_defaults.cpp:151-159`。
- 上の条件を満たすと最終的な READY 前の呼び出しが settle フラグを確認します。さらに、`STRATA_KFD_QUIET` と `STRATA_KFD_QUIET_LOAD` が有効なら expert cache 後にも同じ関数を呼びます。この追加呼び出しは `kfd_quiet::load_moves()` の条件に依存しますが、READY 前の呼び出しはその条件に依存しません。いずれの呼び出しも `STRATA_NO_KFD_SETTLE` 自身の判定を通るため、この変数で両方を止められます。`src/program/generate.cpp:9062-9067, 15161`; `include/strata/core/kfd_quiet.hpp:47-51, 65-68, 81-92`; `include/strata/core/kfd_settle.hpp:140-142`。
- settle フラグが立っていて変数が無効化値でなくても、`/sys/class/kfd/kfd/proc/<pid>/stats_*/evicted_ms` の読み取り可能な counter がなければ待ちません。`include/strata/core/kfd_settle.hpp:71-104, 117-132, 145-148`。

## 実行時の詳細

`generate.cpp` は Linux HIP の GPU 初期化でデバイスの統合属性とアーキテクチャを調べ、対象ならプロセス内 atomic flag を立てます。GPU 初期化に成功しない場合やクラス判定が false の場合、flag は初期値 false のままです。`src/program/generate.cpp:4074-4088, 4121-4123`; `include/strata/core/kfd_settle.hpp:36-41`。

settle 関数は Linux でのみ実装され、呼び出しごとに flag を確認した後、`STRATA_NO_KFD_SETTLE` をその場で `getenv` します。値は static cache されません。コード上は二箇所から呼ばれ得ます。1 回目は expert cache 後、`STRATA_KFD_QUIET` / `STRATA_KFD_QUIET_LOAD` が有効な場合に限られます。2 回目はロード終盤の READY 直前です。環境変数をこの処理の途中で変更した場合、次の呼び出しには反映され得ますが、既に開始した settle を中断する仕組みはありません。`src/program/generate.cpp:9062-9067, 15142-15161`; `include/strata/core/kfd_settle.hpp:138-148`。

待つ場合、settle は `/sys/class/kfd/kfd/proc/<pid>` 以下の `stats_*/evicted_ms` を合算します。counter が初回から読めない・数値でない場合は即時に戻ります。読める場合は 0.2 秒間隔で再読し、合計値が 2 秒間変化しなければ終了します。counter が読めなくなった場合も終了し、初回読み取りから 10 秒で上限終了します。`include/strata/core/kfd_settle.hpp:50-68, 71-104, 113-148`。

## ログと測定値

この settle はログを出しません。対象クラス外、無効化値、counter 不在・不正、静止成立、10 秒上限のいずれでも、この処理からの警告やエラー出力はありません。したがって観測できる違いは、条件を満たす起動時の待ち時間が省略されることです。`include/strata/core/kfd_settle.hpp:136-149`。

ソースコメントは Radeon 780M `gfx1103` の P2006 環境で、登録済み arena のロード直後に counter が動き、初回 prompt の失敗が READY 直後 5/10、30 秒後 0/5、counter 静止 2 秒後 0/10 だったという調査記録を記載しています。これはコメントに記録された条件付き観測で、別環境の性能・正確性を保証する測定値ではありません。`include/strata/core/kfd_settle.hpp:4-15`。`docs/RADEON_780M.md:93-96` は Radeon 780M の GPU reset を概説しますが、この環境変数や settle の挙動を説明してはいません。

## 根拠

- `include/strata/core/kfd_settle.hpp:136-149` — 環境変数の唯一の読み取り箇所、値判定、Linux 条件、待ち時間とログ有無。
- `include/strata/core/kfd_settle.hpp:50-68, 71-104, 113-134` — counter の読み取り・解析・待ちの終了条件。
- `src/program/generate.cpp:4074-4088, 4118-4123`、`src/core/arch_defaults.cpp:151-159` — HIP デバイス分類と対象 GPU クラス。
- `src/program/generate.cpp:9062-9067, 15142-15161`、`include/strata/core/kfd_quiet.hpp:47-51, 65-92` — expert cache 後と READY 前の呼び出し条件。
