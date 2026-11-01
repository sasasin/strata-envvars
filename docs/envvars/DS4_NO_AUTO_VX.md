# `DS4_NO_AUTO_VX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で変更なし。

## 役割

DeepSeek-V4.1 エンジンの Metal ビルドで、自動 VRAM expert 配置にかかるメモリ上限を無効にする opt-out です。`DS4_NO_AUTO_VX` が設定されていると、RAM 使用量を考慮して expert 用 budget を制限する `metal_expert_cap()` を呼びません。GPU の空き容量、`--reserve-mib`、`--vram-experts` の係数から計算する通常の budget は引き続き使われます。この変数自体は expert cache を無効にしたり、expert 数を指定したりしません。

## 値と判定

| 状態 | Metal ビルドで自動配置が選ばれている場合 |
|---|---|
| 未設定 | `metal_expert_cap()` による追加上限を確認する |
| 設定あり | 追加上限の確認をスキップする。空文字を含め、値は問わない |

判定は `std::getenv("DS4_NO_AUTO_VX") == nullptr` の設定有無だけです。`0`、`1`、`false` などの文字列も、空文字と同じく「設定あり」として上限確認をスキップします。数値変換、文字列比較、無効値時の fallback はありません。

`Options` の既定は `vram_experts_auto = true`、`vram_experts = 1.0` です。CLI の `--vram-experts N` を指定すると `N` を `std::atof` で変換して `vram_experts` に設定し、同時に `vram_experts_auto = false` にします。この場合は環境変数が未設定でも Metal 上限を確認しません。したがって明示的な CLI 値がこの自動上限より優先します。

## 有効になる条件

- `src/dsv41/ds4_model.cu` が `STRATA_METAL` 定義下でビルドされていること。同じ分岐は CUDA/HIP 向けにはコンパイルされません。
- `place_experts()` が呼ばれ、`o.vram_experts_auto` が真であること。通常は `Options` の既定値で該当し、`--vram-experts` 指定時には該当しません。
- 環境変数が未設定なら追加上限を計算しますが、計算した cap が当該 budget より小さい場合に限り配置数を減らします。cap が budget 以上なら配置への差はありません。

## 実行時の詳細

`Model::load()` は expert の配置前に `place_experts()` を呼び、その後 `load_experts()` を実行します。`place_experts()` は group member ごとの VRAM budget を計算し、Metal では自動配置かつ `DS4_NO_AUTO_VX` 未設定の場合に `metal_expert_cap()` を呼びます。cap が budget より小さい場合は budget を cap に置き換え、後続の配置計算で VRAM に置く expert 数を決めます。残りの expert は通常の host 側配置の対象です。

`metal_expert_cap()` は物理メモリ、GPU の総メモリ、プロセスの `phys_footprint` 等から cap を計算します。さらに `STRATA_METAL_KEEP_FREE_GB`、`STRATA_METAL_LEAVE_SHARE`、`STRATA_METAL_NEIGHBOURS` を読みます。これらの計算は `DS4_NO_AUTO_VX` が設定されて cap 計算がスキップされる場合には実行されません。

対象変数は `place_experts()` 内で直接 `getenv()` され、static cache はありません。読み取りはモデル読み込み時の配置処理で行われ、生成ごと・リクエストごとの判定ではありません。`--serve` でも `m.load()` の後に serve loop に入るため、同じ初期配置時の判定が使われます。

この変数専用のログやエラーはありません。変数が未設定で cap が budget より小さい場合は stderr に `ds4: expert share: ...` の行が出て budget が制限されます。設定済みの場合や cap が budget 以上の場合、この行は出ません。配置または expert 読み込みが失敗すると `Model::load()` が失敗を返し、CLI は `maya-ds4: <error>` を stderr に出して終了コード 1 を返しますが、これはこの環境変数固有の失敗経路ではありません。

## 根拠

- 候補一覧と完全一致参照: `000_envvers.md:242` に候補名があり、調査対象リポジトリ全体の `rg -n --hidden --glob '!.git/**' 'DS4_NO_AUTO_VX'` では本番コードの参照は `src/dsv41/ds4_model.cu:4619` の1箇所でした。
- Metal ビルド条件、設定有無の判定、budget の cap・ログ: `src/dsv41/ds4_model.cu:4616-4627`。
- cap の計算と関連環境変数: `src/dsv41/ds4_model.cu:4423-4468`。
- `Options` の既定値: `src/dsv41/ds4_model.hpp:25-32`。
- CLI の明示値が自動配置を無効にする処理: `src/dsv41/ds4_main.cpp:1321`。
- `Model::load()` 中の配置・読み込み順: `src/dsv41/ds4_model.cu:3041-3044`。読み込み失敗時の出力と終了: `src/dsv41/ds4_main.cpp:1402-1407`。serve 開始位置: `src/dsv41/ds4_main.cpp:1408-1410`。
- 既存の `docs/DETAILS.md` ではこの変数の説明を確認できませんでした。ここに記した挙動は上記 commit のソースによるものです。
