# `STRATA_KFD_QUIET_NOREG`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux HIP ビルドで Radeon 780M クラスの KFD トポロジーを検出したとき、expert arena を GPU driver に登録しない NOREG 分岐を切り替える環境変数です。未設定時はこの分岐が有効です。arena の割り当て後、`PinnedArena` が登録を省略し、通常は `mlock` も省略します。カーネルや計算内容は変えません。`STRATA_KFD_QUIET` はこの変数を含む共通スイッチです（`include/strata/core/kfd_quiet.hpp:47-51,104-109`）。

## 値と判定

エンジン初期化時に `std::getenv` で `STRATA_KFD_QUIET` とともに値を読み、`noreg_default()` に渡します。共通・個別スイッチのどちらかが先頭文字 `'0'` なら NOREG を無効にし、それ以外（未設定、空文字、`1`、`true`、空白で始まる値、`0` 以外で始まる文字列）は有効側です。文字列全体の比較や数値変換はしません。`STRATA_UMA_REGISTER` が先頭 `'1'` ならスイッチ判定より先に NOREG を無効にします（`include/strata/core/kfd_quiet.hpp:47-51,104-109`; 読み取り元 `src/program/generate.cpp:4133-4136`）。`fix_env(Fix::NoReg)` にもこの名前がありますが、本番コードで `env_on(Fix::NoReg)` を呼ぶ箇所はなく、実際の判定は `generate.cpp` の明示的な `getenv` と `noreg_default()` です（`include/strata/core/kfd_quiet.hpp:54-65`; 本番呼び出し箇所 `src/program/generate.cpp:4133-4136`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_KFD_QUIET` と個別変数の両方 | 両方 unset なら on | 空文字、`1`、`true`、`false`、` 0` | `0`、`0anything` のどちらか一方 |
| `STRATA_UMA_REGISTER` | unset ならスイッチ判定へ | `0`、空文字、`true`（先頭が `1` でない）ならスイッチ判定へ | `1`、`10`、`1anything` は NOREG を off |

この環境変数は CLI 引数や設定ファイルから値を得ません。arena の登録方法には別の上書きがあり、`STRATA_ARENA_PIN_GIB` が空でない場合、値が完全一致で `none` のときだけ未登録、それ以外（例: `0`、`1`、`none `）は登録する扱いです。未設定または空文字ならエンジンの NOREG flag に従います（`include/strata/core/kfd_quiet.hpp:111-115`; `src/core/pinned.cu:583-592`）。

## 有効になる条件

- NOREG の環境判定コードは `STRATA_USE_HIP` かつ `__linux__` のビルドだけにあります。さらにエンジンが integrated gfx11 の KFD quiet クラスと判定する必要があります（`src/program/generate.cpp:4124-4127`、クラス判定は `src/core/arch_defaults.cpp:151-159`）。
- その中でも NOREG 専用条件は `/sys/class/kfd/kfd/topology/nodes` を読み、GPU ノードが1つ以上あり、すべての GPU ノードが gfx1103 の場合だけ成立します。gfx1150、gfx1151、別 GPU の併設、トポロジーを読めない場合は不成立です（`src/program/generate.cpp:4133-4136`; `include/strata/core/kfd_quiet.hpp:214-247`）。
- `STRATA_UMA_REGISTER` の先頭が `1` ならこの分岐は無効です。`STRATA_ARENA_PIN_GIB` の非空値は `PinnedArena` で engine flag より優先し、`none` 以外なら登録します（`include/strata/core/kfd_quiet.hpp:106-115`; `src/core/pinned.cu:583-592`）。
- 効果が現れるのは expert source が arena 経路を使うときです。`--mmap-experts` の file source 経路ではなく、通常の arena 経路で `ArenaExpertSource::open()` が `PinnedArena` を作るときに適用されます（`src/program/generate.cpp:8038-8065,8177-8179,8292-8293`; `src/core/expert_source.cpp:6240-6244`）。
- `STRATA_KFD_QUIET=0` も NOREG を無効にします。`STRATA_ARENA_LOCK` が設定されている場合は、未登録 arena の lock 動作を別途指定します。完全一致 `0` なら lock せず、それ以外の設定値（空文字を含む）は lock を要求します（`include/strata/core/kfd_quiet.hpp:106-122`; `src/core/pinned.cu:800-824`）。

## 実行時の詳細

GPU 情報を得てアーキテクチャ既定値を適用した後、arena を開くより前に一度判定し、true なら `arena_uma_no_register_flag` と `noreg_flag` を true にします。環境値そのものを static cache はしませんが、この判定結果は atomic flag に保存され、後続の arena 作成で使われます。モデル起動中に環境値を変えてもこの保存済み判定は更新されません（`src/program/generate.cpp:4107-4138,8292-8293`; `include/strata/core/kfd_quiet.hpp:97-109`）。

`PinnedArena` は非登録経路で登録範囲を作らず、`STRATA_ARENA_LOCK` が未設定なら通常のページに対する `mlock` も省略します。大ページ backing は lock を呼ばず、`STRATA_ARENA_LOCK` が設定されていれば `0` 以外で lock を試みます。明示的な `STRATA_ARENA_PIN_GIB` は登録方式を上書きします（`src/core/pinned.cu:583-592,795-825`; `include/strata/core/kfd_quiet.hpp:111-122`）。

## ログと測定値

`STRATA_TRACE` が設定されていて NOREG 判定が true なら、標準エラーに `strata trace: kfd quiet: expert arena not registered with the driver, no mlock (...)` を出します。`STRATA_ARENA_PIN_GIB` が登録を指定していても判定自体が true なら行は出て、括弧内は `STRATA_ARENA_PIN_GIB set: registered as it says` になります（`src/program/generate.cpp:4135-4141`）。

arena の作成時には標準エラーに `strata generate: expert arena: ...` を出します。未登録が実際に有効なら note に `NOT registered with the GPU driver (integrated GPU, UMA mode; STRATA_ARENA_PIN_GIB=0 registers it);` が含まれます（`src/core/pinned.cu:825`; `src/program/generate.cpp:8355-8358`）。この環境変数固有の条件を備えた測定値は `docs/DETAILS.md` では確認できませんでした。

## 根拠

- `include/strata/core/kfd_quiet.hpp:47-51,54-65,97-122` — スイッチ判定、動的な環境変数名、NOREG flag と arena 上書き規則。
- `include/strata/core/kfd_quiet.hpp:214-247` — gfx1103 専用の KFD トポロジー条件。
- `src/program/generate.cpp:4124-4141` — HIP/Linux ガード下での判定、flag 設定、trace 行。
- `src/core/pinned.cu:583-592,795-825` — arena の登録・lock 経路と表示 note。
- `src/core/expert_source.cpp:6240-6244`; `src/program/generate.cpp:8038-8065,8177-8179,8292-8293,8355-8358` — arena source の選択、作成、ログ。
