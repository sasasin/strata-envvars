# `DS4_CACHE_DECAY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 専用エンジンの VRAM expert cache が持つ expert ごとの使用熱量を減衰させます。熱量は、CPU 側にある expert を VRAM に入れ、VRAM 側の最も低熱量の expert を出すかどうかの判断に使われます。`DS4_CACHE_DECAY` はキャッシュの入れ替え判断を間接的に変えます。GPU 計算やモデル出力を直接設定する変数ではありません。

この変数は `src/dsv41/ds4_model.cu` の `env_f("DS4_CACHE_DECAY", 0.9f)` で読み取られます。同じファイルに他の参照はありません。共通 helper の `env_f` は、変数が未設定なら既定値を返し、設定されていれば `std::atof` で変換します（`src/dsv41/ds4_model.cu:1165-1168`）。

## 値と判定

`std::atof` の結果を `float` に変換し、値域検査・clamp・無効値警告なしで使います。文字列全体の厳密な数値検査はありません。数値として読める先頭部分を変換し、変換できない文字列や空文字は 0 になります。したがって、たとえば `0.8tail` は `0.8`、`junk` と空文字は `0` として扱われます。負数、1 を超える数も拒否されません。

| 環境変数の状態 | `c_decay` |
|---|---:|
| 未設定 | `0.9` |
| 空文字 | `0` |
| `0` または数値に変換できない文字列 | `0` |
| 数値文字列 | `atof` の変換結果 |
| 負数、1 超の数 | その数値をそのまま使用 |

`NaN` や無限大など、通常の有限値以外を渡した場合もコード上で検査されません。具体的な変換結果は C ランタイムの `atof` 実装に依存します。根拠: `src/dsv41/ds4_model.cu:1165-1168`。

## 有効になる条件

- Strata の DeepSeek-V4.1 専用 `strata-dsv41` エンジン経路で使われます。CMake では `STRATA_BUILD_DSV41` が既定 OFF で、ON かつ `STRATA_HIP_GFX906` でない場合にこの実装を含む実行ファイルを定義します（`CMakeLists.txt:906-920`）。
- `--no-expert-cache` が指定されると `Options::expert_cache` が false になり、cache worker を作らず、`cache_tick_swaps()` も早期 return します。このとき `DS4_CACHE_DECAY` による減衰や VRAM expert の入れ替えは行われません（`src/dsv41/ds4_main.cpp:1331`, `src/dsv41/ds4_model.hpp:37`, `src/dsv41/ds4_model.cu:3158-3173,7250-7252`）。
- キャッシュが有効でも、入れ替えには層に VRAM の spare slot があり、CPU 側の候補 expert と VRAM 側の候補があり、候補間の熱量差が margin 条件を越える必要があります。全 expert が VRAM に収まるなど、入れ替え候補がない場合は、この値を読んでも swap は起きません（`src/dsv41/ds4_model.cu:7341-7355`）。
- `DS4_CACHE_DECAY` の判定自体に OS、CUDA/HIP/Metal、GPU 世代、サーバーモード、モデル状態による別分岐はありません。専用エンジンのビルド・起動と上記キャッシュ条件が適用範囲です。

## 実行時の詳細

値はモデル実装オブジェクトの `c_decay` 初期化時に読み込まれ、通常の処理中に環境変数を変更しても再読込されません。`env_f` 自体は `static` 関数ですが、結果を保存する static cache ではありません。各初期化で呼ばれたときの値がそのオブジェクトの `c_decay` に保持されます（`src/dsv41/ds4_model.cu:1165-1168`）。

熱量は初期配置時に expert profile から設定され（`src/dsv41/ds4_model.cu:4719-4725`）、prompt / decode 中に expert が選ばれると加算されます（例: `src/dsv41/ds4_model.cu:7535-7547,8446-8455,10475-10484`）。各処理後の `cache_tick()` から `cache_tick_swaps(T)` が呼ばれ、`T` を累積した `decay_tokens` が 256 以上になると、カウンターを 0 に戻して全 layer の全 expert の熱量へ `c_decay` を乗算します。大きな `T` でもこの箇所は `if` 一回なので、一回の呼び出しにつき減衰は最大一回です（`src/dsv41/ds4_model.cu:7233-7237,7250-7252,7329-7334`）。

減衰後、CPU 側で今回 hit した候補から最も熱い expert を選び、VRAM 側の最も冷たい expert と比較します。`best_heat > cold_heat * c_margin + c_bonus` のとき swap を queue に入れます。margin と bonus は別の環境変数 `DS4_CACHE_MARGIN`（既定 1.25）と `DS4_CACHE_BONUS`（既定 1.0）から読みます。さらに同時 swap 数は `DS4_CACHE_INFLIGHT` などで制限されます（`src/dsv41/ds4_model.cu:1165-1168,7341-7355`）。

`c_decay=0` なら減衰時に全熱量が 0 になります。0 と 1 の間の値では過去の利用熱量が小さくなり、1 では熱量を保ち、1 より大きい値では増幅し、負数では符号を反転させます。これらは clamp されません。値が不正でも専用の警告・終了経路はなく、その変換結果が上記の比較へ入ります。NaN が実際に得られる場合は比較に使われる熱量も NaN になり得るため、通常の大小比較が成立しない可能性があります。

この変数専用のログはありません。swap 検証用の `DS4_CHECK_SWAPS` が設定された実行では、成功時の expert 移動検証結果や VRAM への移動失敗が stderr に出ますが、そのログは `DS4_CACHE_DECAY` の値や有効状態を示しません（`src/dsv41/ds4_model.cu:1273,7146-7149`）。

## 根拠

`docs/DETAILS.md` と `docs/DEEPSEEK_MAC.md` を照合しましたが、この変数の値判定や測定結果を説明する記述は見つかりませんでした。そのため、性能差や出力への影響は記載せず、現在の挙動はソースコードから確認できる範囲に限っています。

- 読み取り、既定値、変換 helper: `src/dsv41/ds4_model.cu:1163-1168`
- キャッシュを作る条件: `src/dsv41/ds4_model.cu:3158-3173`
- CLI による cache 無効化: `src/dsv41/ds4_main.cpp:1331`; option 既定値は `src/dsv41/ds4_model.hpp:37`
- 熱量の初期化、加算、減衰、swap 判定: `src/dsv41/ds4_model.cu:4719-4725,7329-7355,7535-7547,8446-8455,10475-10484`
- 専用エンジンのビルド条件: `CMakeLists.txt:906-920`
