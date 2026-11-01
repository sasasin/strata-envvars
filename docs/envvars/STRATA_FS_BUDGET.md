# `STRATA_FS_BUDGET`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Foresight swap space が、1 枚のカードにつき 1 回の完了 verify window の間に発行できる expert copy 要求数の上限です。slot 数やコピー対象そのものを指定する変数ではありません。Foresight swap space の作成には別途 `STRATA_FS_SLOTS` が正数である必要があります。

## 値と判定

値は環境変数が設定されていれば `std::atoi` で整数に変換し、結果が 1 未満なら 1 にします。未設定時の既定値は 32 です。値全体の厳密な検証はありません。

| 設定 | `budget` に使う値 |
|---|---:|
| 未設定 | 32 |
| 空文字、数字で始まらない文字列、`0`、負数 | 1（`atoi` の結果が 1 未満のため） |
| 正の整数として変換できる値 | 変換結果 |
| 先頭に空白・符号がある数値、数値の後ろに文字が続く値 | `atoi` が読み取った整数を使い、その後 1 未満なら 1 |

たとえば `" 3x"` は 3、`"-2"` は 1 になります。正値への上限 clamp はありません。`atoi` で `int` の範囲を超える文字列を変換した場合の結果は C/C++ の仕様上保証されないため、その値はここでは規定できません。

CLI 引数、設定ファイル、他の環境変数でこの数値を上書きする経路は確認できません。`STRATA_FS_SLOTS` は機能を作るかどうかを決める独立条件であり、budget 値の優先順位には入りません。

## 有効になる条件

- `foresight_swap_from_env()` が呼ばれ、`STRATA_FS_SLOTS` の `atoi` 結果が正数であること。0 以下なら swap pool を作らず、この変数も読みません。
- その後 `STRATA_VERIFY_DEVICE_PLAN` が設定され `atoi` 結果が 0 以外の場合、swap pool は拒否されます。このとき `STRATA_FS_BUDGET` はすでに読み取られていますが、作られた pool には適用されません。
- swap pool の初期化が成功すること。CUDA device memory、stream または event の確保に失敗した場合は pool が無効になり、budget による copy 制限は発生しません。
- `STRATA_FS_BUDGET` が有効でも、copy 要求があること、該当 expert の blob が pinned source にあること、空き slot があることが必要です。cache hit、peer/remote 経路などで Foresight swap の要求処理に入らない場合、この上限は影響しません。

実装は CUDA runtime API を使う `src/core/expert_source.cpp` の Foresight swap にあり、`src/program/generate.cpp` の generate/serve 経路から pool が接続されます。対象ソース内で `STRATA_FS_BUDGET` の別読み取りはなく、SYCL 側の参照も確認できませんでした。

## 実行時の詳細

pool 初期化時に値を読み、`ForesightSwap::budget` に保存します。`static` cache はありません。各カードについて、`completed` window 番号が変わると発行済み数 `card_used` を 0 に戻します。新しい window で copy 要求が `budget` 件に達すると、それ以上の要求は `over_budget` に数えてその要求の copy を発行せず、通常の expert 処理経路に戻ります。`completed` は generate/serve の window 完了時に増加します。予測 look-ahead による要求も同じ `request_locked()` を通るため同じカード別上限を共有します。

pool の作成に成功すると stderr に `up to %d copies per card and window` として実効 budget を含む初期化行が出ます。処理末尾の report は `... %llu over budget` を出力し、上限により見送られた要求数を示します。初期化失敗時は具体的な理由に `- swap space off` を付けた stderr 行が出ます。コピー API の失敗時は `strata serve: foresight swap: a copy failed - swap space off` が出ます。これらは pool 全体の経路に関するログで、budget の無効値専用の警告や終了経路はありません。

起動後に環境値を変えた場合、すでに作られた pool の budget は変わりません。後続で `foresight_swap_from_env()` が改めて呼ばれれば、その時点の環境値が読み直されます。

## 根拠

- 候補一覧での記載: `docs/envvars/000_envvers.md` の `STRATA_FS_BUDGET`。
- 読み取り順、`atoi`、既定値 32、最低値 1、device-plan による拒否、初期化とログ: `src/core/expert_source.cpp:6537-6562`。
- カード別 window カウンターと budget 判定、超過要求の計上、copy 要求の enqueue: `src/core/expert_source.cpp:6472-6521`。
- 完了 window 数の更新: `src/program/generate.cpp:16581-16587,17056-17059`。
- pool の接続: `src/program/generate.cpp:11109-11121`。
- 遅着 slot の通常経路への fallback および pinned source 条件: `src/core/expert_source.cpp:6404-6418,6483-6488`。
- pool 初期化失敗・copy failure のログ: `src/core/expert_source.cpp:6325-6349,6392-6399`。
- report 文字列と stderr 出力: `src/core/expert_source.cpp:6524-6534`; `src/program/generate.cpp:17177`。
- 関連機能の説明: `include/strata/core/foresight_swap.hpp:2-21`。`docs/DETAILS.md:1030,1437` は Foresight swap slots の概要・測定を記載しますが、`STRATA_FS_BUDGET` 固有の値や性能測定は記載していません。
