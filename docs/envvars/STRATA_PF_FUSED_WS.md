# `STRATA_PF_FUSED_WS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の native fused prompt-expert 経路で、通常の native kernel の代わりに warp-specialized kernel を使う opt-in です。producer warps が重みを F16 に decode し、activation を ring stage に格納する間に、consumer warps が F16 積を計算します。stage ごとの named barrier を使い、decode と積・epilogue を重ねます。通常の native fused 経路や HIP の kernel を有効にする設定ではありません。

## 値と判定

環境変数は `std::getenv()` で読み、値全体の parse ではなく先頭文字だけを比較します。

| 値 | `ws_requested()` の結果 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定ありでも先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` など |
| その他 | 無効。`0`, `true`, ` 1`, `-1` など |

大文字小文字、空白の trim、数値としての妥当性検査はありません。判定結果は `static const bool` に保存され、プロセス内で最初に `ws_requested()` が呼ばれた後に環境を変更しても反映されません。さらに `DevInfo` は GPU ごとに初期化結果を保存するため、setup 結果も同じプロセス内では再評価されません。根拠: `src/prefill/moe_fused_iq.cu:1724-1735,1771-1777`。

## 有効になる条件

- `STRATA_PF_FUSED_WS` が上記の有効値であること。
- CUDA build であること。warp-specialized kernel と setup は `!__HIPCC__` の分岐にあり、HIP では `d.ws` は設定されず、この変数で HIP kernel は切り替わりません（`src/prefill/moe_fused_iq.cu:861,1688,1724-1735,1933-1942`）。
- 対象 GPU で native fused kernels が利用可能であること。CUDA 側は sm_80 未満（sm_75 の限定経路を除く）で native setup を終了し、`d.ok` が立つ必要があります（`src/prefill/moe_fused_iq.cu:1808-1825`）。
- 各 native fused kernel の CUDA attribute、PTX version、dynamic shared-memory 設定、occupancy 確認が成功すること。さらに gate/up と down の全対象形式（および `STRATA_PF_FUSED_Q2N=1` で Q2_0 gate/up が使われる場合はそれも）の WS setup が成功する必要があります（`src/prefill/moe_fused_iq.cu:1728-1735,1846-1852`）。必要な shared memory は WS の stage/table 構成に依存します（`src/prefill/moe_fused_iq.cu:899-900`）。CMake の記述では既定構成は sm_80 / sm_90 で setup され、約 101 KB を収容できない sm_86 / sm_89 / sm_120 などでは利用不可として扱われます（`CMakeLists.txt:2324-2330`）。実行時には実機上の setup 結果が判定になります。
- Prefill が native fused 経路を選ぶこと。実際の layer 判定では `stream_all`、peer device 不使用、native expert layout、Hadamard 未使用、native 対応形式などが必要です。Q2_0 pack などでは `STRATA_PF_FUSED` の値または既定条件も経路選択に関わります（`src/prefill/prefill.cpp:4192-4223`; `src/prefill/moe_fused_iq.cu:1976-2015`）。小さい chunk は MMQ 経路を保ち、fused 経路のバッファが chunk に不足する場合は明示的な失敗になります（`src/prefill/prefill.cpp:4195-4198,4224-4235`）。

この変数単独で native fused prompt 経路を有効化するわけではありません。たとえば `STRATA_PF_FUSED=0` は native layer の選択を拒否し、`STRATA_PF_FUSED_NATIVE=0` も native fused 経路を拒否します（`src/prefill/moe_fused_iq.cu:1976-1990`）。一方、`STRATA_PF_FUSED` が未設定でも対応形式・GPU などの既定条件により native fused 経路が選ばれる場合があります（同 `:1981-2015`）。CLI 引数による `STRATA_PF_FUSED_WS` の上書きはこの読み取り経路にはありません。`STRATA_PF_BATCH` は expert batch 数を決めますが、WS kernel の選択条件そのものではありません（`src/prefill/prefill.cpp:4273-4279`）。

## 実行時の詳細

`dev_info()` の初期化中に、native setup が成功した場合だけ WS setup を試します。`d.ws` が true なら native `Batch` overload は `WideBatch` overload に移り、そこで全対象の launch に `ws=true` を渡します。CUDA launch helper は `ws` を最初に判定し、`native_ws_kernel` を起動します。したがって `STRATA_PF_FUSED_F16=1` も同時に設定されている場合、WS が setup 済みなら WS launch が選ばれます。`STRATA_PF_FUSED_NT=256` は独立して NT kernel setup を行いますが、WS が選ばれた launch は `ws` 分岐が優先されます（`src/prefill/moe_fused_iq.cu:1837-1852,1926-1943,2113-2119,2141-2172`）。

WS setup が失敗した場合も `d.ws` は false のままで、native fused path 自体が有効なら通常の native kernel に fallback します。`d.ok` が true かつ WS が要求されて setup に失敗した場合は stderr に `prefill fused experts (native): STRATA_PF_FUSED_WS=1 is not available here` を出します。`d.ok` 自体が false の経路ではこの WS 不可ログは出ません。fused prompt path が実際に走ると、最初の一度だけ stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` が出ますが、このログは WS 選択を識別しません（`src/prefill/moe_fused_iq.cu:1846-1852`; `src/prefill/prefill.cpp:4252-4257`）。

## 根拠

- WS kernel の producer / consumer 構成と stage overlap: `src/prefill/moe_fused_iq.cu:861-868,906-912`。
- 環境値の読み取り、cache、kernel setup: `src/prefill/moe_fused_iq.cu:1724-1735,1846-1853`。
- CUDA/HIP と GPU 条件、native fused 経路の条件: `src/prefill/moe_fused_iq.cu:1771-1825,1976-2015`。
- prefill から WS kernel launch まで: `src/prefill/prefill.cpp:4192-4223,4252-4262`; `src/prefill/moe_fused_iq.cu:1926-1943,2113-2119,2141-2172`。
- Strata の資料は WS が約 101 KB の shared memory を必要とし、例示された測定で一層 7.65 ms と記載しています。これは PR author による CMP 170HX の報告値で、Strata 側の独自測定ではありません。本書では性能や出力特性を一般化しません（`docs/DETAILS.md:1535-1544`）。
