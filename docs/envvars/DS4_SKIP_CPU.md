# `DS4_SKIP_CPU`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 engine の host CPU lane に割り当てられた expert の計算を省略する、Metal engine 内の計測用スイッチです。通常の推論結果を保つための設定ではありません。CPU lane が担当する出力は計算されないまま後段の合成へ渡されるため、モデル出力に影響します。

## 値と判定

`ds4_dbg("DS4_SKIP_CPU")` は Metal build では `std::getenv(name) != nullptr` を返します。値を文字列や数値として parse しません。

| 状態 | Metal build での判定 |
|---|---|
| 未設定 | CPU lane を通常どおり実行 |
| 空文字を含む設定済み値 | CPU lane を省略 |
| その他の設定済み値（`0`, `false`, `1` など） | CPU lane を省略 |

CUDA/HIP build では `ds4_dbg(const char*)` が `constexpr false` と定義されるため、この名前について環境を読みません。したがって CUDA/HIP では値にかかわらず CPU lane を省略しません。

## 有効になる条件

- `strata_ds4` の Metal build であること。`metal/CMakeLists.txt` は `ds4_model.cu` を `strata_ds4` に含め、target に `STRATA_METAL=1` を定義します。
- host-routed の layer で CPU lane の expert entry（`ents`）が1件以上あること。entry が空なら判定箇所に入りません。
- CUDA/HIP build では helper が常に false を返すので効果はありません。

CLI 引数や他の設定による優先順位はありません。関連する `DS4_FAKE_CPU_US` は、CPU lane を省略した場合に限り、設定されていれば `atoi` で変換した microseconds の sleep を行う別の計測用設定です。これは省略した CPU 計算の結果を補いません。

## 実行時の詳細

host-routed MoE 経路では、GPU に置かれていない routed experts を `ents` にまとめます。`ents` が空でない場合、初回に `DS4_SKIP_CPU` の有無を判定し、その結果を関数内の `static const bool` に cache します。プロセス実行中に環境を変えても再評価されません。未設定なら `cpu_experts(l, h_x, ents)` が host expert を計算します。設定済みならその呼び出しを飛ばし、`DS4_FAKE_CPU_US` が設定されている場合だけ代わりに sleep します。

CPU 計算を飛ばした場合も、後続処理は `c_yd` の各 slot を重み付きで `h_part` に集計し、`d.cpu_part` に転送して `combine(...)` を実行します。`c_yd` は通常 CPU expert 計算の出力先であり、skip 分岐では初期化・再計算されません。このためCPU lane の出力が欠落し、初回の未使用 slot ではゼロ初期値、以降は以前の内容が残っていればそれを集計する可能性があります。GPU 側では error や fallback は発生せず、この MoE 出力で後続 layer の計算が続きます。

この変数自体の有効・無効を示すログや警告はありません。Metal build で `DS4_CPU_LOG` も設定すると、CPU lane 区間の累積時間・call 数・expert 数を終了時に stderr へ `cpu lane calls: ...` と出します。skip 時の時間には設定した fake sleep と合成・転送までが含まれ、expert 数も実際に計算した数ではなく `ents.size()` の累計です。通常の CPU lane と同じ計測値として解釈できません。

## 根拠

- 候補一覧の `DS4_SKIP_CPU` は `docs/envvars/000_envvers.md` にあります（Strata リポジトリ側の調査対象ファイルではなく候補名の出所）。Strata ソース内の完全一致検索では実装参照は `src/dsv41/ds4_model.cu:10561` の1箇所です。
- helper の Metal 環境読み取りと非 Metal 常時 false: `src/dsv41/ds4_launch.h:30-36`。
- DeepSeek-V4.1 Metal target のソース組み込みと macro: `metal/CMakeLists.txt:135-146,165-170`。CUDA/HIP target の `strata-dsv41` 組み込み: `CMakeLists.txt:918-920`。
- CPU lane entry の構築と、GPU resident expert との分類: `src/dsv41/ds4_model.cu:10463-10523`。
- skip 判定、任意の fake sleep、CPU 出力集計、ログ、転送、後続合成: `src/dsv41/ds4_model.cu:10555-10582`。
- `c_yd` の確保: `src/dsv41/ds4_model.cu:3032-3040`。通常計算で `c_yd` に expert 出力を書き込む例: `src/dsv41/ds4_model.cu:6529-6540`。
